import { act, createRoot, App, fillInput, signedInApp } from "../../test-support/app";

test("login shows BillTrack branding and labeled sign-in fields", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  const root = createRoot(container);
  act(() => root.render(<App />));
  expect(container.querySelector('img[alt="BillTrack"]').getAttribute("src")).toBe("/static/billtrack-icon.png");
  expect(container.querySelector('.login-visual img').getAttribute("src")).toBe("/static/billtrack-logo.png");
  expect(container.querySelector('input[autocomplete="username"]')).not.toBeNull();
  expect(container.querySelector('input[autocomplete="current-password"]')).not.toBeNull();
  expect(container.querySelector('a[href="/accounts/signup/"]').textContent).toBe('Create account');
  expect(container.querySelector('a[href="/accounts/password-reset/"]').textContent).toContain('email');
  expect(container.querySelector('a[href="/accounts/verify-email/"]')).not.toBeNull();
  expect(container.querySelector('button[type="submit"]').textContent).toContain("Sign in");
  expect(container.querySelector('.project-identity').textContent).toContain("Part of the Estate Management System");
  expect(container.querySelector('.project-identity').textContent).toContain("An Open Internet Project");
  const projectLink = container.querySelector('.project-identity a');
  expect(projectLink.textContent).toBe("An Open Internet");
  expect(projectLink.getAttribute("href")).toBe("https://www.anopeninternet.eu.org/");
  expect(container.querySelector('.project-credits').textContent).toContain("Conceptualized by Rajarshi Bhadra.");
  expect(container.querySelector('.project-credits').textContent).toContain("Development Support: Claude — initial implementation; Codex — enhancements, optimization, and advanced functionality.");
  act(() => root.unmount());
});

test('login errors remain inline until dismissed, with no disappearing timer', async () => {
  global.IS_REACT_ACT_ENVIRONMENT=true;
  global.fetch=jest.fn(async () => ({ ok:false,status:401,json:async () => ({error:'Invalid credentials'}) }));
  const container=document.createElement('div');document.body.appendChild(container);
  const root=createRoot(container);
  try {
    await act(async () => root.render(<App />));
    jest.useFakeTimers();
    await act(async () => container.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    expect(container.querySelector('.login-panel [role="alert"]').textContent).toContain('Invalid credentials');
    act(() => jest.advanceTimersByTime(10000));
    expect(container.querySelector('.login-panel [role="alert"]').textContent).toContain('Invalid credentials');
    act(() => container.querySelector('button[aria-label="Dismiss error"]').click());
    expect(container.querySelector('.login-panel [role="alert"]')).toBeNull();
  } finally { act(() => root.unmount());container.remove();jest.useRealTimers(); }
});

test('temporary startup authentication failure preserves the token and offers retry', async () => {
  global.IS_REACT_ACT_ENVIRONMENT=true;
  localStorage.setItem('token','saved-token');
  let fail=true;
  global.fetch=jest.fn(async url => {
    if (url.includes('/auth/me/')) {
      if (fail) throw new TypeError('Failed to fetch');
      return {ok:true,json:async () => ({username:'tester'})};
    }
    return {ok:true,json:async () => url.includes('/dashboard/') ? {} : []};
  });
  const container=document.createElement('div');document.body.appendChild(container);const root=createRoot(container);
  try {
    await act(async () => root.render(<App />));
    expect(localStorage.getItem('token')).toBe('saved-token');
    expect(container.querySelector('[role="alert"]').textContent).toMatch(/connection|reach/i);
    fail=false;
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent==='Retry sign-in check').click());
    expect(container.querySelector('h1').textContent).toBe('Dashboard');
  } finally { act(() => root.unmount());container.remove(); }
});

test('expired credentials preserve an open form until sign-in navigation is confirmed', async () => {
  const {container,close}=await signedInApp((url,options) => options.method==='POST' && url.endsWith('/payments/')
    ? Promise.resolve({ok:false,status:401,json:async () => ({detail:'Invalid token.'})}) : null);
  const confirm=jest.spyOn(window,'confirm').mockReturnValue(false);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent==='Bills').click());
    act(() => [...container.querySelectorAll('button')].find(node => node.textContent==='Pay').click());
    const input=container.querySelector('#paymentform-principal-amount');
    act(() => fillInput(input,'75'));
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent==='Record Payment').click());
    expect(input.value).toBe('75');
    const signIn=container.querySelector('dialog button[data-sign-in]');
    expect(signIn).not.toBeNull();
    act(() => signIn.click());
    expect(confirm).toHaveBeenCalled();
    expect(input.value).toBe('75');
    confirm.mockReturnValue(true);
    act(() => signIn.click());
    expect(container.querySelector('.login-panel')).not.toBeNull();
  } finally {close();confirm.mockRestore();}
});

test('an older success notification cannot dismiss a newer error', async () => {
  jest.useFakeTimers();
  const open=jest.spyOn(window,'open').mockReturnValue(null);
  const {container,close}=await signedInApp();
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent==='Bills').click());
    act(() => [...container.querySelectorAll('button')].find(node => node.textContent==='Invoice').click());
    act(() => jest.advanceTimersByTime(4000));
    expect(container.querySelector('[role="alert"]').textContent).toContain('Allow pop-ups');
  } finally {close();open.mockRestore();jest.useRealTimers();}
});

test('login offers the existing authenticator recovery route', async () => {
  localStorage.clear();
  const container=document.createElement('div');document.body.appendChild(container);
  const root=createRoot(container);
  try {
    await act(async () => root.render(<App />));
    const link=[...container.querySelectorAll('a')].find(node=>node.textContent==='Forgot password? Use authenticator');
    expect(link).toBeDefined();
    expect(link.getAttribute('href')).toBe('/admin/password-reset/totp/');
  } finally {act(()=>root.unmount());container.remove();}
});
