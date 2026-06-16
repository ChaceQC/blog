import { ArrowRight, GitBranch, Mail, Rss, Send } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { listPublicPosts } from '../../features/posts/api.ts'
import {
  formatPostDate,
  formatRelativePostDate,
} from '../../features/posts/postMeta.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import { listPublicSiteItems } from '../../features/sites/api.ts'

export function HomePage() {
  const {
    data: postsData,
    isError: isPostsError,
    isLoading: isPostsLoading,
  } = useQuery({
    queryKey: ['public-posts', 'home'],
    queryFn: () => listPublicPosts({ limit: 5 }),
  })
  const {
    data: sitesData,
    isError: isSitesError,
    isLoading: isSitesLoading,
  } = useQuery({
    queryKey: ['public-site-items', 'home'],
    queryFn: () => listPublicSiteItems({ limit: 3 }),
  })
  const featuredPosts = postsData?.items ?? []
  const featuredSites = sitesData?.items ?? []
  const socialIconMap = {
    GitHub: GitBranch,
    RSS: Rss,
    Email: Mail,
  }

  return (
    <div className="page-flow">
      <section className="hero-section">
        <div className="hero-identity">
          <img
            className="hero-avatar"
            src={siteSettings.avatarUrl}
            alt={`${siteSettings.owner} 的头像`}
          />
          <h1>{siteSettings.description}</h1>
          <p className="hero-lead">
            一间安静的小站，用来放文章、素材、友链和一些常去的入口。
          </p>
          <div className="hero-quote">
            <span>{siteSettings.quote}</span>
            <small>
              {siteSettings.stats.map((stat) => stat.value).join(' · ')}
            </small>
          </div>
          <div className="social-strip" aria-label="社交链接">
            {siteSettings.socialLinks.map((link) => (
              <a href={link.url} key={link.label}>
                {(() => {
                  const Icon =
                    socialIconMap[link.label as keyof typeof socialIconMap]

                  return Icon ? (
                    <Icon size={16} strokeWidth={1.6} aria-hidden="true" />
                  ) : (
                    link.label
                  )
                })()}
                <span className="sr-only">{link.label}</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      <div className="home-board">
        <section className="content-section recent-section">
          <div className="section-heading section-heading--stacked">
            <small>RECENT WRITING</small>
            <span>近期笔墨</span>
          </div>
          <div className="recent-list">
            {featuredPosts.map((post, index) => (
              <Link
                className="recent-item"
                to={`/posts/${post.slug}`}
                key={post.id}
              >
                <span className="recent-item__index">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="recent-item__body">
                  <span className="recent-item__meta">
                    文章 · {formatPostDate(post.published_at)}
                  </span>
                  <strong>{post.title}</strong>
                  <small>{post.summary ?? post.seo_description ?? '暂无摘要'}</small>
                </span>
                <time>{formatRelativePostDate(post.published_at)}</time>
              </Link>
            ))}
            {isPostsLoading ? (
              <p className="empty-state">正在整理近期文章。</p>
            ) : null}
            {isPostsError ? (
              <p className="empty-state">文章服务暂时不可用。</p>
            ) : null}
            {!isPostsLoading && !isPostsError && featuredPosts.length === 0 ? (
              <p className="empty-state">还没有公开发布的文章。</p>
            ) : null}
          </div>
          <Link className="timeline-link" to="/posts">
            翻阅完整时间线
          </Link>
        </section>

        <aside className="side-column">
          <div className="note-panel">
            <div className="section-heading section-heading--stacked">
              <small>MUSINGS</small>
              <span>碎念</span>
            </div>
            <div className="musing-list">
              <p>「先把字句放稳，页面自然会慢慢有自己的呼吸。」</p>
              <small>2026年6月15日星期一</small>
              <p>「UI 的留白不是空，是让内容有地方沉下来。」</p>
              <small>2026年6月15日星期一</small>
            </div>
          </div>

          <div className="note-panel note-panel--letter">
            <div className="section-heading section-heading--stacked">
              <small>LETTERS</small>
              <span>来信</span>
            </div>
            <p>如果你也在搭一个长期维护的小站，欢迎交换友链。</p>
            <Link className="inline-link" to="/links">
              <Mail size={15} strokeWidth={1.8} aria-hidden="true" />
              查看友链
            </Link>
          </div>
        </aside>
      </div>

      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>GATEWAYS</small>
          <span>常用入口</span>
          <Link to="/sites">打开目录</Link>
        </div>
        <div className="gateway-list">
          {featuredSites.map((site) => (
            <a href={site.url} key={site.id}>
              <Send size={15} strokeWidth={1.7} aria-hidden="true" />
              <span>
                <strong>{site.title}</strong>
                <small>{site.description ?? site.group_name ?? '常用入口'}</small>
              </span>
            </a>
          ))}
          {isSitesLoading ? (
            <p className="empty-state">正在整理常用入口。</p>
          ) : null}
          {isSitesError ? (
            <p className="empty-state">站点目录暂时不可用。</p>
          ) : null}
          {!isSitesLoading && !isSitesError && featuredSites.length === 0 ? (
            <p className="empty-state">还没有公开入口。</p>
          ) : null}
        </div>
      </section>

      <section className="closing-section">
        <span>仲夏蝉鸣</span>
        <strong>欢迎来信</strong>
        <Link className="text-button" to="/posts">
          阅读文章
          <ArrowRight size={17} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      </section>
    </div>
  )
}
