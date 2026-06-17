import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import {
  listAccessLogs,
  listAuditLogs,
  listLoginLogs,
  listSecurityEvents,
} from '../../features/logs/api.ts'
import { formatChinaDateTime } from '../../utils/datetime.ts'

import type {
  AccessLogItem,
  AuditLogItem,
  LoginLogItem,
  SecurityEventItem,
} from '../../features/logs/types.ts'

const LIST_PAGE_SIZE = 10

type LogTab = 'audit' | 'access' | 'login' | 'security'
type LogRecord =
  | { tab: 'audit'; item: AuditLogItem }
  | { tab: 'access'; item: AccessLogItem }
  | { tab: 'login'; item: LoginLogItem }
  | { tab: 'security'; item: SecurityEventItem }

const tabLabels = {
  audit: '操作',
  access: '访问',
  login: '登录',
  security: '事件',
} satisfies Record<LogTab, string>

export function AdminLogsPage() {
  const [activeTab, setActiveTab] = useState<LogTab>('audit')
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const auditLogsQuery = useQuery({
    queryKey: ['admin-audit-logs'],
    queryFn: listAuditLogs,
  })
  const accessLogsQuery = useQuery({
    queryKey: ['admin-access-logs'],
    queryFn: listAccessLogs,
  })
  const loginLogsQuery = useQuery({
    queryKey: ['admin-login-logs'],
    queryFn: listLoginLogs,
  })
  const securityEventsQuery = useQuery({
    queryKey: ['admin-security-events'],
    queryFn: listSecurityEvents,
  })
  const records = useMemo<LogRecord[]>(() => {
    if (activeTab === 'audit') {
      return (auditLogsQuery.data?.items ?? []).map((item) => ({
        tab: 'audit',
        item,
      }))
    }
    if (activeTab === 'access') {
      return (accessLogsQuery.data?.items ?? []).map((item) => ({
        tab: 'access',
        item,
      }))
    }
    if (activeTab === 'login') {
      return (loginLogsQuery.data?.items ?? []).map((item) => ({
        tab: 'login',
        item,
      }))
    }
    return (securityEventsQuery.data?.items ?? []).map((item) => ({
      tab: 'security',
      item,
    }))
  }, [
    accessLogsQuery.data,
    activeTab,
    auditLogsQuery.data,
    loginLogsQuery.data,
    securityEventsQuery.data,
  ])
  const safeListPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(records.length / LIST_PAGE_SIZE) - 1),
  )
  const visibleRecords = useMemo(
    () =>
      records.slice(
        safeListPage * LIST_PAGE_SIZE,
        safeListPage * LIST_PAGE_SIZE + LIST_PAGE_SIZE,
      ),
    [records, safeListPage],
  )
  const selectedRecord =
    records.find((record) => logKey(record) === selectedKey) ??
    visibleRecords[0] ??
    null
  const activeQuery = {
    audit: auditLogsQuery,
    access: accessLogsQuery,
    login: loginLogsQuery,
    security: securityEventsQuery,
  }[activeTab]

  function switchTab(tab: LogTab) {
    setActiveTab(tab)
    setSelectedKey(null)
    setListPage(0)
  }

  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>记录</span>
        <h1>日志</h1>
      </section>

      <section className="admin-panel">
        <div className="admin-tabs" role="tablist" aria-label="日志类型">
          {(Object.keys(tabLabels) as LogTab[]).map((tab) => (
            <button
              aria-selected={activeTab === tab}
              className={activeTab === tab ? 'admin-tab active' : 'admin-tab'}
              key={tab}
              onClick={() => switchTab(tab)}
              role="tab"
              type="button"
            >
              {tabLabels[tab]}
            </button>
          ))}
        </div>

        {activeQuery.isError ? (
          <p className="form-error">{tabLabels[activeTab]}日志暂时打不开</p>
        ) : null}

        <div className="log-browser">
          <div className="log-list" role="tabpanel">
            {visibleRecords.map((record) => (
              <button
                className={
                  logKey(record) === logKey(selectedRecord)
                    ? 'content-row active'
                    : 'content-row'
                }
                key={logKey(record)}
                onClick={() => setSelectedKey(logKey(record))}
                type="button"
              >
                <LogSummary record={record} />
              </button>
            ))}
            {activeQuery.isLoading ? (
              <p className="empty-state">正在读取{tabLabels[activeTab]}日志。</p>
            ) : null}
            {!activeQuery.isLoading && records.length === 0 ? (
              <p className="empty-state">暂无{tabLabels[activeTab]}日志。</p>
            ) : null}
            <ListPager
              page={safeListPage}
              pageSize={LIST_PAGE_SIZE}
              totalItems={records.length}
              isLoading={activeQuery.isLoading}
              variant="admin"
              onPageChange={(nextPage) => {
                setListPage(nextPage)
                setSelectedKey(null)
              }}
            />
          </div>

          <aside className="log-detail">
            {selectedRecord ? (
              <LogDetail record={selectedRecord} />
            ) : (
              <p className="empty-state">选择一条记录查看详情。</p>
            )}
          </aside>
        </div>
      </section>
    </div>
  )
}

function LogSummary({ record }: { record: LogRecord }) {
  if (record.tab === 'audit') {
    return (
      <span>
        <strong>{record.item.action}</strong>
        <small>
          {formatEntity(record.item.entity_type, record.item.entity_id)} ·{' '}
          {formatDate(record.item.created_at)}
        </small>
        <small>{record.item.ip ?? '未知 IP'}</small>
      </span>
    )
  }
  if (record.tab === 'access') {
    return (
      <span>
        <strong>{record.item.access_type}</strong>
        <small>
          {record.item.method} · {record.item.status_code} ·{' '}
          {formatDate(record.item.created_at)}
        </small>
        <small>{record.item.path}</small>
      </span>
    )
  }
  if (record.tab === 'login') {
    return (
      <span>
        <strong>{record.item.username}</strong>
        <small>
          {record.item.success ? '登录成功' : record.item.reason ?? '登录失败'} ·{' '}
          {formatDate(record.item.created_at)}
        </small>
        <small>{record.item.ip ?? '未知 IP'}</small>
      </span>
    )
  }
  return (
    <span>
      <strong>{record.item.event_type}</strong>
      <small>
        {record.item.severity} · {formatDate(record.item.created_at)}
      </small>
      <small>{record.item.path ?? '无路径'}</small>
    </span>
  )
}

function LogDetail({ record }: { record: LogRecord }) {
  const rows = detailRows(record)
  return (
    <div className="admin-detail">
      <dl className="detail-list">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      <pre className="log-json">{formatJson(detailJson(record))}</pre>
    </div>
  )
}

function detailRows(record: LogRecord): Array<{ label: string; value: string }> {
  if (record.tab === 'audit') {
    return [
      { label: '动作', value: record.item.action },
      { label: '对象', value: formatEntity(record.item.entity_type, record.item.entity_id) },
      { label: '操作者', value: record.item.actor_id === null ? '未知' : `#${record.item.actor_id}` },
      { label: 'IP', value: record.item.ip ?? '未知' },
      { label: '时间', value: formatDate(record.item.created_at) },
      { label: 'UA', value: record.item.user_agent ?? '未知' },
    ]
  }
  if (record.tab === 'access') {
    return [
      { label: '类型', value: record.item.access_type },
      { label: '路径', value: record.item.path },
      { label: '状态', value: String(record.item.status_code) },
      { label: '对象', value: formatEntity(record.item.entity_type, record.item.entity_id) },
      { label: 'IP', value: record.item.ip ?? '未知' },
      { label: '时间', value: formatDate(record.item.created_at) },
      { label: 'UA', value: record.item.user_agent ?? '未知' },
    ]
  }
  if (record.tab === 'login') {
    return [
      { label: '用户', value: record.item.username },
      { label: '结果', value: record.item.success ? '成功' : '失败' },
      { label: '原因', value: record.item.reason ?? '无' },
      { label: 'IP', value: record.item.ip ?? '未知' },
      { label: '时间', value: formatDate(record.item.created_at) },
      { label: 'UA', value: record.item.user_agent ?? '未知' },
    ]
  }
  return [
    { label: '事件', value: record.item.event_type },
    { label: '等级', value: record.item.severity },
    { label: '路径', value: record.item.path ?? '无' },
    { label: 'IP', value: record.item.ip ?? '未知' },
    { label: '时间', value: formatDate(record.item.created_at) },
    { label: 'UA', value: record.item.user_agent ?? '未知' },
  ]
}

function detailJson(record: LogRecord): Record<string, unknown> | null {
  if (record.tab === 'audit') {
    return {
      before: record.item.before_json,
      after: record.item.after_json,
    }
  }
  if (record.tab === 'login') {
    return null
  }
  return record.item.detail_json
}

function logKey(record: LogRecord | null): string {
  if (!record) {
    return ''
  }
  return `${record.tab}-${record.item.id}`
}

function formatEntity(type: string | null, id: number | null): string {
  if (!type) {
    return '未关联'
  }
  return id === null ? type : `${type} #${id}`
}

function formatDate(value: string): string {
  return formatChinaDateTime(value, '未知时间')
}

function formatJson(value: Record<string, unknown> | null): string {
  if (!value) {
    return '{}'
  }
  return JSON.stringify(value, null, 2)
}
