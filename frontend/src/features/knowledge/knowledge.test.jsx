import { act, fillInput, signedInApp } from '../../test-support/app';

test('staff can search for a guide and follow a related guide inside BillTrack', async () => {
  const { container, close } = await signedInApp();
  const button = text => [...container.querySelectorAll('button')]
    .find(entry => entry.textContent.startsWith(text));

  try {
    await act(async () => button('Knowledge Base').click());
    expect(button('Knowledge Base').getAttribute('aria-current')).toBe('page');
    const search = container.querySelector('#guide-search');
    const article = container.querySelector('#knowledge-guide');
    expect(article.textContent).toContain('Record allotment for this shop');

    act(() => fillInput(search, 'windows tutorial'));
    expect(button('Windows installation tutorial')).toBeDefined();
    expect(button('Linux installation tutorial')).toBeUndefined();
    await act(async () => button('Windows installation tutorial').click());
    expect(article.textContent).toContain('PowerShell');
    expect(document.activeElement).toBe(article);

    const backupLink = article.querySelector('a[data-guide="BACKUP-RESTORE"]');
    await act(async () => backupLink.click());
    expect(article.querySelector('h2').textContent).toBe('Backups and recovery');
    expect(article.querySelector('pre')).not.toBeNull();

    act(() => fillInput(search, 'no-such-guide'));
    expect(container.querySelector('.knowledge-index [role="status"]').textContent)
      .toBe('No guides match your search.');
  } finally { close(); }
});
