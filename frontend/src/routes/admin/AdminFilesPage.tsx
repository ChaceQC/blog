import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LockKeyhole, Search, UploadCloud } from 'lucide-react'
import { useMemo, useState, type ChangeEvent } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import {
  deleteAdminFile,
  getAdminFileTemporaryUrl,
  listAdminFiles,
  uploadAdminFile,
} from '../../features/files/api.ts'
import { FileDetail } from '../../features/files/FileDetail.tsx'
import { useAuth } from '../../features/auth/useAuth.ts'
import { parseApiTime } from '../../utils/datetime.ts'

import type {
  AdminFileItem,
  AdminFileTemporaryUrlResponse,
  FileVisibility,
} from '../../features/files/types.ts'

const visibilityLabels = {
  public: '公开',
  private: '私有',
} satisfies Record<FileVisibility, string>
const uploadMaxSizeBytes = 30 * 1024 * 1024
const LIST_PAGE_SIZE = 8

export function AdminFilesPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [visibility, setVisibility] = useState<FileVisibility>('public')
  const [publicListed, setPublicListed] = useState(false)
  const [altText, setAltText] = useState('')
  const [articleSlug, setArticleSlug] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const [temporaryUrls, setTemporaryUrls] = useState<
    Record<number, AdminFileTemporaryUrlResponse>
  >({})

  const filesQuery = useQuery({
    queryKey: ['admin-files'],
    queryFn: listAdminFiles,
  })
  const files = useMemo(
    () => {
      const allFiles = filesQuery.data?.items ?? []
      return allFiles.filter((file) => {
        const keyword = query.trim().toLowerCase()
        if (!keyword) {
          return true
        }
        return (
          file.original_name.toLowerCase().includes(keyword) ||
          file.object_key.toLowerCase().includes(keyword) ||
          file.mime_type.toLowerCase().includes(keyword)
        )
      })
    },
    [filesQuery.data, query],
  )
  const safeListPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(files.length / LIST_PAGE_SIZE) - 1),
  )
  const visibleFiles = useMemo(
    () =>
      files.slice(
        safeListPage * LIST_PAGE_SIZE,
        safeListPage * LIST_PAGE_SIZE + LIST_PAGE_SIZE,
      ),
    [files, safeListPage],
  )
  const selectedFile =
    files.find((file) => file.id === selectedId) ?? files[0] ?? null

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      if (!uploadFile) {
        throw new Error('请选择要上传的文件')
      }
      if (uploadFile.size > uploadMaxSizeBytes) {
        throw new Error('文件超过 30MB，请压缩后再上传')
      }
      return uploadAdminFile(
        uploadFile,
        visibility,
        altText,
        publicListed,
        session.csrfToken,
      )
    },
    onSuccess: (file) => {
      queryClient.invalidateQueries({ queryKey: ['admin-files'] })
      setSelectedId(file.id)
      setUploadFile(null)
      setAltText('')
      setPublicListed(false)
      setNotice('文件已上传')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '上传失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedFile) {
        throw new Error('当前文件无法删除')
      }
      return deleteAdminFile(selectedFile.id, session.csrfToken)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-files'] })
      setSelectedId(null)
      setNotice('文件已移入清理队列')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '删除失败')
    },
  })

  const temporaryUrlMutation = useMutation({
    mutationFn: getAdminFileTemporaryUrl,
    onSuccess: (link, fileId) => {
      setTemporaryUrls((current) => ({ ...current, [fileId]: link }))
      setNotice('访问链接已生成')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '访问链接生成失败')
    },
  })

  async function getTemporaryUrl(file: AdminFileItem): Promise<string | null> {
    if (file.visibility !== 'public') {
      setNotice('私有文件只在后台可见')
      return null
    }

    const cached = temporaryUrls[file.id]
    if (cached && parseApiTime(cached.expires_at) > Date.now() + 5000) {
      return cached.url
    }

    const link = await temporaryUrlMutation.mutateAsync(file.id)
    return link.url
  }

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>素材</span>
        <h1>文件夹</h1>
        <button
          className="text-button admin-heading__action"
          disabled={!session || !uploadFile || uploadMutation.isPending}
          onClick={() => uploadMutation.mutate()}
          type="button"
        >
          <UploadCloud size={17} strokeWidth={1.8} aria-hidden="true" />
          {uploadMutation.isPending ? '上传中' : '上传文件'}
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>素材列表</span>
            <small>{filesQuery.isLoading ? '加载中' : `共 ${files.length} 件`}</small>
          </div>
          {filesQuery.isError ? <p className="form-error">素材列表暂时打不开</p> : null}
          <label className="admin-search">
            <Search size={16} strokeWidth={1.8} aria-hidden="true" />
            <input
              onChange={(event) => {
                setQuery(event.target.value)
                setListPage(0)
              }}
              placeholder="搜索文件名、MIME 或 key"
              value={query}
            />
          </label>
          <div className="content-list">
            {visibleFiles.map((file) => (
              <button
                className={
                  file.id === selectedFile?.id ? 'content-row active' : 'content-row'
                }
                key={file.id}
                onClick={() => setSelectedId(file.id)}
                type="button"
              >
                <span>
                  <strong>{file.original_name}</strong>
                  <small>
                    ID {file.id} ·{' '}
                    {file.visibility === 'public'
                      ? file.public_listed
                        ? '公开文件栏'
                        : '文章可引用'
                      : '仅后台可见'}
                  </small>
                </span>
                <small>{visibilityLabels[file.visibility]}</small>
              </button>
            ))}
          </div>
          <ListPager
            page={safeListPage}
            pageSize={LIST_PAGE_SIZE}
            totalItems={files.length}
            isLoading={filesQuery.isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
          {!filesQuery.isLoading && files.length === 0 ? (
            <p className="empty-state">没有匹配的文件。</p>
          ) : null}
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>素材详情</span>
            <small>{notice ?? '保存在本机'}</small>
          </div>
          {selectedFile ? (
            <FileDetail
              file={selectedFile}
              isDeleting={deleteMutation.isPending}
              isLinkLoading={
                temporaryUrlMutation.isPending &&
                temporaryUrlMutation.variables === selectedFile.id
              }
              articleSlug={articleSlug}
              getTemporaryUrl={getTemporaryUrl}
              onDelete={() => deleteMutation.mutate()}
              onArticleSlugChange={setArticleSlug}
              setNotice={setNotice}
              temporaryUrl={temporaryUrls[selectedFile.id] ?? null}
            />
          ) : (
            <p className="empty-state">请选择或上传一份素材。</p>
          )}
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>上传说明</span>
            <small>
              <LockKeyhole size={14} strokeWidth={1.8} aria-hidden="true" />
              文件夹
            </small>
          </div>
          <form className="content-form">
            <label>
              文件
              <input
                accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                onChange={(event) => handleFileChange(event, setUploadFile)}
                type="file"
              />
            </label>
            <div className="form-grid form-grid--two">
              <label>
                可见性
                <select
                  onChange={(event) => {
                    const nextVisibility = event.target.value as FileVisibility
                    setVisibility(nextVisibility)
                    if (nextVisibility === 'private') {
                      setPublicListed(false)
                    }
                  }}
                  value={visibility}
                >
                  <option value="public">公开</option>
                  <option value="private">私有</option>
                </select>
              </label>
              <label className="checkbox-field">
                <input
                  checked={publicListed}
                  disabled={visibility !== 'public'}
                  onChange={(event) => setPublicListed(event.target.checked)}
                  type="checkbox"
                />
                展示在公开文件栏
              </label>
              <label>
                替代文本
                <input
                  onChange={(event) => setAltText(event.target.value)}
                  placeholder="用于图片说明"
                  value={altText}
                />
              </label>
            </div>
          </form>
          <div className="admin-note-list">
            <p>可以上传 JPEG、PNG、GIF、WebP 和 PDF，单个文件不超过 30MB。</p>
            <p>文章图片使用渲染接口，公开文件栏下载才生成短时链接。</p>
            <p>删除后会先从列表移走，后面再统一清理原文件。</p>
          </div>
        </section>
      </div>
    </div>
  )
}

function handleFileChange(
  event: ChangeEvent<HTMLInputElement>,
  setUploadFile: (file: File | null) => void,
) {
  setUploadFile(event.target.files?.[0] ?? null)
}
