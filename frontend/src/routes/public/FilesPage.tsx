import { useMutation, useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'

import { publicErrorMessage } from '../../api/client.ts'
import { ListPager } from '../../components/ListPager.tsx'
import {
  getPublicFileTemporaryUrl,
  listPublicFiles,
} from '../../features/files/api.ts'
import type { PublicFileItem } from '../../features/files/types.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { useQueryPage } from '../../hooks/useQueryPage.ts'
import { formatChinaDateTime } from '../../utils/datetime.ts'

const PAGE_SIZE = 8
const pageDescription = '公开发布的附件会显示在这里。'
const emptyFiles: PublicFileItem[] = []

export function FilesPage() {
  const { page, setPage } = useQueryPage()
  const [notice, setNotice] = useState<string | null>(null)
  const filesQuery = useQuery({
    queryKey: ['public-files', page],
    queryFn: ({ signal }) =>
      listPublicFiles({ limit: PAGE_SIZE, offset: page * PAGE_SIZE, signal }),
  })
  const temporaryUrlMutation = useMutation({
    mutationFn: (fileId: number) => getPublicFileTemporaryUrl(fileId),
    onError: (error) =>
      setNotice(publicErrorMessage(error, '下载链接暂时无法生成。')),
  })
  const files = filesQuery.data?.items ?? emptyFiles
  const totalFiles = filesQuery.data?.total ?? 0
  const filesErrorMessage = publicErrorMessage(
    filesQuery.error,
    '文件列表暂时不可用。',
  )
  usePageSeo({
    title: '文件',
    description: pageDescription,
    path: '/files',
    keywords: '公开文件,附件,资料',
  })

  async function openFile(file: PublicFileItem) {
    try {
      const link = await temporaryUrlMutation.mutateAsync(file.id)
      window.open(link.url, '_blank', 'noopener,noreferrer')
      setNotice(`链接有效至 ${formatChinaDateTime(link.expires_at, '未知时间')}`)
    } catch (error) {
      setNotice(publicErrorMessage(error, '下载链接暂时无法生成。'))
    }
  }

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>资料</small>
        <h1>文件</h1>
        <p>{pageDescription}</p>
      </section>

      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>列表</small>
          <span>公开文件</span>
          <small>{filesQuery.isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {notice ? <p className="empty-state">{notice}</p> : null}
        {filesQuery.isError ? <p className="empty-state">{filesErrorMessage}</p> : null}
        {!filesQuery.isLoading && !filesQuery.isError && totalFiles === 0 ? (
          <p className="empty-state">还没有公开文件。</p>
        ) : null}
        <div className="compact-list">
          {files.map((file) => (
            <button
              className="compact-row"
              disabled={temporaryUrlMutation.isPending}
              key={file.id}
              onClick={() => void openFile(file)}
              type="button"
            >
              <span>
                <strong>{file.original_name}</strong>
                <small>
                  {file.mime_type} · {formatFileSize(file.size_bytes)}
                </small>
              </span>
              <span className="compact-row__meta">
                <Download size={16} strokeWidth={1.8} aria-hidden="true" />
              </span>
            </button>
          ))}
        </div>
        <ListPager
          page={page}
          pageSize={PAGE_SIZE}
          totalItems={totalFiles}
          isLoading={filesQuery.isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )

}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
}
