import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

/* ─── Simple markdown → HTML renderer ─── */

/**
 * Convert a markdown string to an array of HTML element configs,
 * then render them as React nodes.
 *
 * Supports: headings, paragraphs, bold, inline code, code blocks,
 * unordered lists, tables, horizontal rules, blockquotes.
 */
function mdLineToHtml(line: string): string {
  // escape HTML entities first, then apply markdown formatting
  let html = line.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  // bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // inline code
  html = html.replace(/`(.+?)`/g, '<code class="rounded bg-muted px-1 py-0.5 text-xs font-mono text-foreground">$1</code>')
  return html
}

function renderMdToReact(md: string): React.ReactNode[] {
  const lines = md.split('\n')
  const nodes: React.ReactNode[] = []
  let key = 0
  let i = 0

  const push = (node: React.ReactNode) => {
    nodes.push(<div key={key++}>{node}</div>)
  }

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // ── Horizontal rule ──
    if (/^---+\s*$/.test(trimmed)) {
      push(<hr className="my-4 border-border" />)
      i++
      continue
    }

    // ── Heading ──
    const headingMatch = trimmed.match(/^(#{2,3})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length // 2 or 3
      const text = headingMatch[2]
      const Tag = level === 2 ? 'h2' : 'h3'
      push(
        <Tag className={`font-semibold text-foreground mt-6 mb-2 ${level === 2 ? 'text-base' : 'text-sm'}`}>
          <span dangerouslySetInnerHTML={{ __html: mdLineToHtml(text) }} />
        </Tag>,
      )
      i++
      continue
    }

    // ── Code block ──
    if (trimmed.startsWith('```')) {
      i++
      const codeLines: string[] = []
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      push(
        <pre className="rounded-lg bg-muted p-3 my-2 overflow-x-auto text-xs leading-relaxed font-mono text-foreground">
          <code>{codeLines.join('\n')}</code>
        </pre>,
      )
      continue
    }

    // ── Unordered list ──
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const items: React.ReactNode[] = []
      while (i < lines.length) {
        const t = lines[i].trim()
        const listMatch = t.match(/^[-*]\s+(.+)$/)
        if (!listMatch) break
        items.push(
          <li className="text-xs text-foreground/90 leading-relaxed">
            <span dangerouslySetInnerHTML={{ __html: mdLineToHtml(listMatch[1]) }} />
          </li>,
        )
        i++
      }
      push(<ul className="list-disc pl-5 space-y-1 my-2">{items}</ul>)
      continue
    }

    // ── Table ──
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const rows: React.ReactNode[] = []
      let isHeader = true
      while (i < lines.length) {
        const t = lines[i].trim()
        if (!t.startsWith('|') || !t.endsWith('|')) break
        // skip separator row (|---|)
        if (/^\|[\s-:]+\|$/.test(t)) { i++; isHeader = false; continue }
        const cells = t.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
        const Tag = isHeader ? 'th' : 'td'
        rows.push(
          <tr className={`${isHeader ? '' : 'border-t border-border'}`}>
            {cells.map((c, ci) => (
              <Tag key={ci} className={`px-3 py-1.5 text-xs ${isHeader ? 'font-medium text-foreground' : 'text-foreground/80'}`}>
                <span dangerouslySetInnerHTML={{ __html: mdLineToHtml(c.trim()) }} />
              </Tag>
            ))}
          </tr>,
        )
        i++
      }
      push(
        <div className="overflow-x-auto my-3">
          <table className="w-full border-collapse rounded-lg border border-border">
            <thead className="bg-muted">{rows.filter((_, idx) => idx === 0 || (rows[idx - 1] as any)?.type === 'th')}</thead>
            <tbody>{rows.filter((_, idx) => idx > 0 && (rows[idx - 1] as any)?.type === 'th').map(r => r)}</tbody>
          </table>
        </div>,
      )
      continue
    }

    // ── Blockquote ──
    if (trimmed.startsWith('> ')) {
      const quoteLines: string[] = []
      while (i < lines.length) {
        const t = lines[i].trim()
        if (!t.startsWith('> ')) break
        quoteLines.push(t.slice(2))
        i++
      }
      push(
        <blockquote className="border-l-2 border-primary/40 pl-3 my-2 text-xs text-muted-foreground italic">
          {quoteLines.map((q, qi) => (
            <span key={qi} dangerouslySetInnerHTML={{ __html: mdLineToHtml(q) + (qi < quoteLines.length - 1 ? '<br/>' : '') }} />
          ))}
        </blockquote>,
      )
      continue
    }

    // ── Empty line ──
    if (trimmed === '') {
      i++
      continue
    }

    // ── Paragraph ──
    push(
      <p className="text-xs text-foreground/80 leading-relaxed my-1.5">
        <span dangerouslySetInnerHTML={{ __html: mdLineToHtml(trimmed) }} />
      </p>,
    )
    i++
  }

  return nodes
}

/* ════════════════════════════════════════════════════
   UsageGuide
   ════════════════════════════════════════════════════ */
export default function UsageGuide({ embedded }: { embedded?: boolean }) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/api/usage-guide')
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.text()
      })
      .then((text) => {
        if (!cancelled) {
          setContent(text)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    if (embedded) {
      return <div className="py-8 text-center text-xs text-muted-foreground">加载中…</div>
    }
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-center text-xs text-muted-foreground">加载中…</p>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    if (embedded) {
      return <div className="py-8 text-center text-xs text-destructive">加载失败：{error}</div>
    }
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-center text-xs text-destructive">加载失败：{error}</p>
        </CardContent>
      </Card>
    )
  }

  if (embedded) {
    return (
      <div className="px-5 py-4">
        <div className="space-y-0.5">
          {renderMdToReact(content ?? '')}
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>使用说明</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[70vh]">
          <div className="space-y-0.5 pr-3">
            {renderMdToReact(content ?? '')}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
