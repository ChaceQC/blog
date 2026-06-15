import { ArrowRight, PenLine } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PostList } from '../../features/posts/PostList.tsx'
import { samplePosts } from '../../features/posts/samplePosts.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { sampleSites } from '../../features/sites/sampleSites.ts'

export function HomePage() {
  const featuredPosts = samplePosts.slice(0, 2)
  const featuredSites = sampleSites.slice(0, 2)

  return (
    <div className="page-flow">
      <section className="intro-section">
        <div>
          <p className="eyebrow">
            <PenLine size={17} strokeWidth={1.8} aria-hidden="true" />
            {siteSettings.owner}
          </p>
          <h1>{siteSettings.description}</h1>
          <p>
            草稿、已发布文章、文件素材、友链和站点导航共享同一个可维护的工作台。
          </p>
          <Link className="text-button" to="/posts">
            阅读文章
            <ArrowRight size={17} strokeWidth={1.8} aria-hidden="true" />
          </Link>
        </div>
        <img
          className="intro-section__image"
          src="https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80"
          alt=""
        />
      </section>

      <section className="content-section">
        <div className="section-heading">
          <span>最新文章</span>
          <Link to="/posts">查看全部</Link>
        </div>
        <PostList posts={featuredPosts} />
      </section>

      <section className="content-section">
        <div className="section-heading">
          <span>站点导航</span>
          <Link to="/sites">打开目录</Link>
        </div>
        <SiteGrid sites={featuredSites} />
      </section>
    </div>
  )
}
