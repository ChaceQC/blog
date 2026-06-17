import argparse
import asyncio
from getpass import getpass

from app.core.database import AsyncSessionLocal
from app.repositories.admin_bootstrap import AdminBootstrapRepository
from app.services.admin_bootstrap import (
    AdminBootstrapService,
    InitialAdminCommand,
    InitialAdminExistsError,
)
from app.tasks.encryption import cleanup_expired_encryption_sessions
from app.tasks.files import (
    DeletedFileCleanupCommand,
    OrphanFileCleanupCommand,
    cleanup_deleted_files,
    cleanup_orphan_files,
)
from app.tasks.links import FriendLinkHealthCheckCommand, check_friend_links


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "create-admin":
        asyncio.run(_create_admin(args))
        return
    if args.command == "cleanup-encryption-sessions":
        asyncio.run(_cleanup_encryption_sessions())
        return
    if args.command == "cleanup-deleted-files":
        asyncio.run(_cleanup_deleted_files(args))
        return
    if args.command == "cleanup-orphan-files":
        asyncio.run(_cleanup_orphan_files(args))
        return
    if args.command == "check-friend-links":
        asyncio.run(_check_friend_links(args))
        return

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blog-admin")
    subparsers = parser.add_subparsers(dest="command")

    create_admin = subparsers.add_parser(
        "create-admin",
        help="创建初始后台管理员",
    )
    create_admin.add_argument("--username", required=True, help="管理员用户名")
    create_admin.add_argument("--email", required=True, help="管理员邮箱")
    create_admin.add_argument("--display-name", help="管理员展示名")
    create_admin.add_argument(
        "--password",
        help="管理员密码；省略时使用交互式输入",
    )
    subparsers.add_parser(
        "cleanup-encryption-sessions",
        help="清理已过期的应用层加密会话",
    )
    cleanup_files = subparsers.add_parser(
        "cleanup-deleted-files",
        help="清理已软删除且无引用的本地文件",
    )
    cleanup_files.add_argument(
        "--older-than-days",
        type=_non_negative_int,
        default=7,
        help="只清理早于该天数的软删除文件，默认 7 天",
    )
    cleanup_files.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="单次最多扫描的软删除文件数量，默认 100",
    )
    cleanup_orphans = subparsers.add_parser(
        "cleanup-orphan-files",
        help="扫描或清理本地孤儿文件",
    )
    cleanup_orphans.add_argument(
        "--limit",
        type=_positive_int,
        default=1000,
        help="单次最多扫描的本地文件数量，默认 1000",
    )
    cleanup_orphans.add_argument(
        "--delete",
        action="store_true",
        help="实际删除孤儿文件；省略时只演练扫描结果",
    )
    check_links = subparsers.add_parser(
        "check-friend-links",
        help="检查已通过友链的 HTTP 状态",
    )
    check_links.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="单次最多检查的友链数量，默认 100",
    )
    check_links.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=5.0,
        help="单个友链请求超时时间，默认 5 秒",
    )
    return parser


async def _create_admin(args: argparse.Namespace) -> None:
    password = args.password or _prompt_password()
    command = InitialAdminCommand(
        username=args.username,
        email=args.email,
        password=password,
        display_name=args.display_name,
    )

    async with AsyncSessionLocal() as session:
        service = AdminBootstrapService(AdminBootstrapRepository(session))
        try:
            user = await service.create_initial_admin(command)
        except InitialAdminExistsError as exc:
            raise SystemExit(f"创建失败：{exc}") from exc

    print(f"已创建初始管理员：{user.username} <{user.email}>")


async def _cleanup_encryption_sessions() -> None:
    deleted_count = await cleanup_expired_encryption_sessions()
    print(f"已清理过期加密会话：{deleted_count} 条")


async def _cleanup_deleted_files(args: argparse.Namespace) -> None:
    result = await cleanup_deleted_files(
        DeletedFileCleanupCommand(
            older_than_days=args.older_than_days,
            limit=args.limit,
        ),
    )
    print(
        "已清理软删除文件："
        f"扫描 {result.scanned_files} 条，"
        f"删除记录 {result.deleted_records} 条，"
        f"删除物理文件 {result.deleted_objects} 个，"
        f"缺失物理文件 {result.missing_objects} 个，"
        f"跳过 {result.skipped_files} 条",
    )


async def _cleanup_orphan_files(args: argparse.Namespace) -> None:
    result = await cleanup_orphan_files(
        OrphanFileCleanupCommand(
            limit=args.limit,
            dry_run=not args.delete,
        ),
    )
    mode = "演练扫描" if result.dry_run else "实际清理"
    print(
        f"已完成孤儿文件{mode}："
        f"扫描 {result.scanned_files} 个，"
        f"已登记 {result.tracked_files} 个，"
        f"孤儿 {result.orphan_files} 个，"
        f"删除 {result.deleted_files} 个，"
        f"跳过 {result.skipped_files} 个",
    )
    if result.orphan_object_keys:
        preview = "、".join(result.orphan_object_keys[:10])
        suffix = "……" if len(result.orphan_object_keys) > 10 else ""
        print(f"孤儿文件示例：{preview}{suffix}")


async def _check_friend_links(args: argparse.Namespace) -> None:
    result = await check_friend_links(
        FriendLinkHealthCheckCommand(
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        ),
    )
    print(
        "已完成友链状态检查："
        f"扫描 {result.scanned_links} 条，"
        f"正常 {result.healthy_links} 条，"
        f"异常 {result.unhealthy_links} 条，"
        f"访问失败 {result.failed_links} 条",
    )


def _prompt_password() -> str:
    password = getpass("管理员密码：")
    confirmation = getpass("再次输入密码：")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致")
    if not password:
        raise SystemExit("管理员密码不能为空")
    return password


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("不能小于 0")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


if __name__ == "__main__":
    main()
