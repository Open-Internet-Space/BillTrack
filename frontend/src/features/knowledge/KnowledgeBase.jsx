import { useEffect, useRef, useState } from 'react';
import guides from './guide-content.generated.json';
import './knowledge.css';

const categories = [...new Set(guides.map(guide => guide.category))];

export function KnowledgeBase() {
  const [query, setQuery] = useState('');
  const [selection, setSelection] = useState({ id: guides[0].id });
  const article = useRef(null);
  const selected = guides.find(guide => guide.id === selection.id);
  const terms = query.trim().toLowerCase().split(/\s+/);
  const matches = guides.filter(guide => {
    const text = `${guide.title} ${guide.description} ${guide.category}`.toLowerCase();
    return terms.every(term => text.includes(term));
  });

  useEffect(() => {
    if (!selection.focus) return;
    const heading = document.getElementById(selection.anchor);
    const target = article.current.contains(heading) ? heading : article.current;
    target.focus({ preventScroll: true });
    target.scrollIntoView?.({ block: 'start' });
  }, [selection]);

  const open = (id, anchor) => setSelection({ id, anchor, focus: true });
  const followGuideLink = event => {
    const link = event.target.closest('a[data-guide]');
    if (!link) return;
    event.preventDefault();
    open(link.dataset.guide, link.hash.slice(1));
  };

  return (
    <section className="knowledge-base" aria-labelledby="knowledge-title">
      <h1 id="knowledge-title" className="page-title">Knowledge Base</h1>
      <div className="knowledge-layout">
        <nav className="knowledge-index" aria-label="Help guides">
          <label htmlFor="guide-search">Find a guide</label>
          <input className="inp" type="search" id="guide-search" placeholder="Try invoices or renewals"
            value={query} onChange={event => setQuery(event.target.value)} />
          {categories.map(category => {
            const group = matches.filter(guide => guide.category === category);
            if (!group.length) return null;
            return (
              <section key={category}>
                <h2>{category}</h2>
                <ul>{group.map(guide => (
                  <li key={guide.id}>
                    <button type="button" aria-current={guide.id === selected.id ? 'true' : undefined}
                      onClick={() => open(guide.id)}>
                      <strong>{guide.title}</strong>
                      <span>{guide.description}</span>
                    </button>
                  </li>
                ))}</ul>
              </section>
            );
          })}
          {matches.length === 0 && <p role="status">No guides match your search.</p>}
        </nav>
        <article className="knowledge-article" id="knowledge-guide" tabIndex={-1} ref={article}
          aria-label={selected.title} onClick={followGuideLink}>
          <div dangerouslySetInnerHTML={{ __html: selected.html }} />
        </article>
      </div>
    </section>
  );
}
