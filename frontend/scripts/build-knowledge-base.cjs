const fs = require('node:fs');
const path = require('node:path');
const MarkdownIt = require('markdown-it');

const guides = [
  ['Daily work', 'ESTATE-WORKFLOW', 'Allotment register and estate workflows', 'Find allotments, record terms and handovers, and track expiry, charges and deposits.'],
  ['Daily work', 'EXTENSIONS-AND-SECURITY-DEPOSITS', 'Extensions and security deposits', 'Assess and print extension fees, link renewals, review and carry forward deposits, and record date exceptions.'],
  ['Daily work', 'LISTS-AND-FILTERS', 'Find records and use filters', 'Search, filter, refresh and move through bills, payments and allotments.'],
  ['Billing and collections', 'RECEIPT-BILLING', 'Legacy bill receipt and deadlines', 'Confirm receipt and understand the five-day rule for older bills.'],
  ['Billing and collections', 'INVOICES-AND-SETTINGS', 'Print invoices and set invoice layout', 'Print one bill or a selection and manage invoice branding.'],
  ['Billing and collections', 'REPORTS', 'Reports and exports', 'Review estate dues, cash receipts, held security and historical reports.'],
  ['Billing and collections', 'EMAIL-DRAFTS', 'Prepare email drafts', 'Create and review a draft with bill details before sending.'],
  ['Billing and collections', 'EMAIL-REMINDERS', 'Review dues reminders', 'Preview reminders and confirm delivery from Django Admin.'],
  ['Administration', 'ACTIVITY-HISTORY', 'Review activity and corrections', 'Find changes to records and the reasons behind corrections.'],
  ['Administration', 'ADMIN-DATA-TRANSFER', 'Export and restore business data', 'Review a version 2 export and choose Merge or Replace.'],
  ['Administration', 'BACKUP-RESTORE', 'Back up and recover BillTrack', 'Create a verified backup and rehearse restoration.'],
  ['Administration', 'ERRORS-AND-RECOVERY', 'Troubleshoot and recover', 'Interpret error references and recover from interrupted work.'],
  ['Administration', 'EMAIL-ACCOUNTS', 'Sign-in and account approval', 'Manage approved accounts, email verification and password recovery.'],
  ['Administration', 'SETUP-WINDOWS', 'Windows installation tutorial', 'Install BillTrack locally, verify it and set up backups.'],
  ['Administration', 'SETUP-LINUX', 'Linux installation tutorial', 'Install BillTrack on Linux and configure the service and backups.'],
];

const docs = path.resolve(__dirname, '../../docs');
const markdown = new MarkdownIt({ html: false });
const allowed = new Set(guides.map(([, file]) => file));
const renderToken = (tokens, index, options, env, renderer) => renderer.renderToken(tokens, index, options);

markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const href = token.attrGet('href');
  const local = href.match(/^(?:\.\/)?([\w-]+)\.md(?:#([\w-]+))?$/i);
  if (local && allowed.has(local[1])) {
    token.attrSet('data-guide', local[1]);
    token.attrSet('href', local[2] ? `#${local[2]}` : '#knowledge-guide');
  } else if (!/^(?:https?:\/\/|#)/i.test(href)) {
    const end = tokens.findIndex((item, position) => position > index && item.type === 'link_close');
    if (end !== -1) tokens[end].hidden = true;
    return '';
  }
  return renderToken(tokens, index, options, env, renderer);
};
markdown.renderer.rules.link_close = (tokens, index, ...options) =>
  tokens[index].hidden ? '' : renderToken(tokens, index, ...options);

markdown.renderer.rules.heading_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const slug = tokens[index + 1].content.toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, '').trim().replace(/\s+/g, '-');
  const count = env.headingCounts.get(slug) || 0;
  env.headingCounts.set(slug, count + 1);
  token.attrSet('id', count ? `${slug}-${count}` : slug);
  token.attrSet('tabindex', '-1');
  const tag = `h${Math.min(Number(token.tag.slice(1)) + 1, 6)}`;
  token.tag = tag;
  tokens[index + 2].tag = tag;
  return renderToken(tokens, index, options, env, renderer);
};

const catalog = guides.map(([category, id, title, description]) => {
  const source = fs.readFileSync(path.join(docs, `${id}.md`), 'utf8');
  return { category, id, title, description, html: markdown.render(source, { headingCounts: new Map() }) };
});
fs.writeFileSync(path.resolve(__dirname, '../src/features/knowledge/guide-content.generated.json'), JSON.stringify(catalog));
