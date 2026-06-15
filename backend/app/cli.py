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


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "create-admin":
        asyncio.run(_create_admin(args))
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


def _prompt_password() -> str:
    password = getpass("管理员密码：")
    confirmation = getpass("再次输入密码：")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致")
    if not password:
        raise SystemExit("管理员密码不能为空")
    return password


if __name__ == "__main__":
    main()
