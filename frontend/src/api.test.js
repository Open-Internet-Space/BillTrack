import API from "./api";

beforeEach(() => { API.logout(); API.onUnauthorized = null; global.fetch = jest.fn(); });
afterEach(() => { delete global.fetch; API.logout(); API.onUnauthorized = null; jest.useRealTimers(); });

test('validation messages survive, but server details are replaced with a safe reference', async () => {
  global.fetch.mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({ amount: ['Enter a positive amount'] }) });
  await expect(API.post('/payments/', {})).rejects.toThrow('amount: Enter a positive amount');
  global.fetch.mockResolvedValueOnce({ ok: false, status: 500, headers: new Headers({ 'X-Request-ID': 'abc-123' }),
    json: async () => ({ detail: 'private database/password failure' }) });
  try { await API.post('/payments/', {}); } catch (error) {
    expect(error.message).toContain('Check records before retrying');
    expect(error.message).toContain('Reference: abc-123');
    expect(error.message).not.toContain('private');
    expect(error.uncertain).toBe(true);
  }
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test('HTML failures and unreadable successful writes get useful messages', async () => {
  global.fetch.mockResolvedValueOnce({ ok: false, status: 502, json: async () => { throw new SyntaxError('HTML'); } });
  await expect(API.get('/tenants/')).rejects.toThrow('BillTrack ran into a problem');
  global.fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => { throw new SyntaxError('HTML'); } });
  await expect(API.post('/payments/', {})).rejects.toMatchObject({ uncertain: true, message: expect.stringContaining('unreadable response') });
});

test('offline writes are uncertain and are never automatically repeated', async () => {
  global.fetch.mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(API.post('/bills/', {})).rejects.toMatchObject({ uncertain: true, message: expect.stringContaining('Check records before retrying') });
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('requests time out after sixty seconds and stop waiting', async () => {
  jest.useFakeTimers();
  global.fetch.mockImplementation((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  }));
  const result = expect(API.get('/tenants/')).rejects.toThrow('60 seconds');
  jest.advanceTimersByTime(60000);
  await result;
  expect(jest.getTimerCount()).toBe(0);
});

test('response body downloads are covered by the same timeout', async () => {
  jest.useFakeTimers();
  global.fetch.mockImplementation(async (url, options) => ({ ok: true, status: 200,
    blob: () => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))) }));
  const result = expect(API.document('/invoice/1/')).rejects.toThrow('60 seconds');
  await Promise.resolve();
  jest.advanceTimersByTime(60000);
  await result;
});

test('only protected-resource 401 responses notify the signed-in app', async () => {
  API.onUnauthorized = jest.fn();
  global.fetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'Invalid credentials' }) });
  await expect(API.login('bad', 'bad')).rejects.toThrow('Invalid credentials');
  await expect(API.get('/auth/me/')).rejects.toThrow('sign-in has expired');
  expect(API.onUnauthorized).not.toHaveBeenCalled();
  await expect(API.get('/bills/')).rejects.toThrow('sign-in has expired');
  expect(API.onUnauthorized).toHaveBeenCalledTimes(1);
});

test('uploads preserve multipart boundaries and report field errors', async () => {
  API.token = 'upload-token';
  global.fetch.mockResolvedValue({ ok: false, status: 400, json: async () => ({ file: ['Choose an image'] }) });
  await expect(API.upload('/settings/', new FormData())).rejects.toThrow('file: Choose an image');
  const options = global.fetch.mock.calls[0][1];
  expect(options.headers.Authorization).toBe('Token upload-token');
  expect(options.headers['Content-Type']).toBeUndefined();
});

test('failed report downloads do not claim a financial save or create a file', async () => {
  global.fetch.mockRejectedValue(new TypeError('Offline'));
  try { await API.download('/reports/', {}, 'report.pdf'); } catch (error) {
    expect(error.message).toContain('Could not reach BillTrack');
    expect(error.message).not.toContain('saved');
    expect(error.uncertain).toBe(false);
  }
});

test('successful empty delete responses are accepted', async () => {
  global.fetch.mockResolvedValue({ ok: true, status: 204 });
  await expect(API.delete('/bills/1/')).resolves.toBeNull();
});

test('HTML downloads and JSON invoice bodies are not mistaken for documents', async () => {
  global.fetch.mockResolvedValueOnce({ ok: true, status: 200,
    blob: async () => new Blob(['<html>Login</html>'], { type: 'text/html' }) });
  await expect(API.download('/reports/', {}, 'report.pdf')).rejects.toThrow('unreadable response');
  global.fetch.mockResolvedValueOnce({ ok: true, status: 200,
    blob: async () => new Blob(['{"detail":"failure"}'], { type: 'application/json' }) });
  await expect(API.document('/invoice/1/')).rejects.toThrow('unreadable response');
});

test('browser download failures are readable and clean up temporary links', async () => {
  const oldCreate = URL.createObjectURL;
  URL.createObjectURL = jest.fn(() => { throw new Error('private browser details'); });
  global.fetch.mockResolvedValue({ ok: true, status: 200,
    blob: async () => new Blob(['PDF'], { type: 'application/pdf' }) });
  try {
    await expect(API.download('/reports/', {}, 'report.pdf')).rejects.toThrow('Allow downloads for BillTrack');
    expect(document.querySelector('a[download="report.pdf"]')).toBeNull();
  } finally { URL.createObjectURL = oldCreate; }
});
