import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  listAccessLogs,
  listAuditLogs,
  listLoginLogs,
  listSecurityEvents,
} from '../../features/logs/api.ts'
import type {
  LogRecord,
  LogTab,
} from '../../features/logs/AdminLogBrowser.tsx'
import {
  AdminLogBrowser,
} from '../../features/logs/AdminLogBrowser.tsx'

const LIST_PAGE_SIZE = 10

export function AdminLogsPage() {
  const [activeTab, setActiveTab] = useState<LogTab>('audit')
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const logQueryParams = {
    limit: LIST_PAGE_SIZE,
    offset: listPage * LIST_PAGE_SIZE,
  }
  const auditLogsQuery = useQuery({
    queryKey: ['admin-audit-logs', logQueryParams],
    queryFn: () => listAuditLogs(logQueryParams),
    enabled: activeTab === 'audit',
  })
  const accessLogsQuery = useQuery({
    queryKey: ['admin-access-logs', logQueryParams],
    queryFn: () => listAccessLogs(logQueryParams),
    enabled: activeTab === 'access',
  })
  const loginLogsQuery = useQuery({
    queryKey: ['admin-login-logs', logQueryParams],
    queryFn: () => listLoginLogs(logQueryParams),
    enabled: activeTab === 'login',
  })
  const securityEventsQuery = useQuery({
    queryKey: ['admin-security-events', logQueryParams],
    queryFn: () => listSecurityEvents(logQueryParams),
    enabled: activeTab === 'security',
  })
  const activeQuery = {
    audit: auditLogsQuery,
    access: accessLogsQuery,
    login: loginLogsQuery,
    security: securityEventsQuery,
  }[activeTab]
  const allFetchedRecords = useMemo<LogRecord[]>(() => {
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
  const records = allFetchedRecords
  const exactTotalItems = activeQuery.data?.total
  const totalItems =
    exactTotalItems ?? (listPage > 0 ? listPage * LIST_PAGE_SIZE + 1 : records.length)
  const pagerPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(totalItems / LIST_PAGE_SIZE) - 1),
  )

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

      <AdminLogBrowser
        activeTab={activeTab}
        records={records}
        selectedKey={selectedKey}
        page={pagerPage}
        pageSize={LIST_PAGE_SIZE}
        totalItems={totalItems}
        isLoading={activeQuery.isLoading}
        isFetching={activeQuery.isFetching}
        isError={activeQuery.isError}
        onPageChange={setListPage}
        onSelectKey={setSelectedKey}
        onSwitchTab={switchTab}
      />
    </div>
  )
}
