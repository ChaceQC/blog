import { X } from 'lucide-react'
import { useEffect, useId, type ReactNode } from 'react'

type AdminModalProps = {
  children: ReactNode
  className?: string
  description?: ReactNode
  isOpen: boolean
  onClose: () => void
  title: string
}

export function AdminModal({
  children,
  className,
  description,
  isOpen,
  onClose,
  title,
}: AdminModalProps) {
  const titleId = useId()

  useEffect(() => {
    if (!isOpen) {
      return
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) {
    return null
  }

  return (
    <div
      className="admin-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
      role="presentation"
    >
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className={className ? `admin-modal ${className}` : 'admin-modal'}
        role="dialog"
      >
        <div className="admin-modal__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <small>{description}</small> : null}
          </div>
          <button
            aria-label="关闭"
            className="icon-button admin-modal__close"
            onClick={onClose}
            type="button"
          >
            <X size={17} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>
        <div className="admin-modal__body">{children}</div>
      </section>
    </div>
  )
}
