import { act, signedInApp, fillInput, sampleBill } from "../../test-support/app";
const generated={allottee_id:1,allottee_name:"Test Allottee",template_id:1,bill_ids:[1],to:"vendor@example.invalid",cc:"authority@example.invalid",subject:"Invoice details",body:"Prepared wording",calculated_at:"2026-11-10T08:00:00Z"};
const button=(container,text)=>[...container.querySelectorAll("button")].find(b=>b.textContent===text);
test('Prepare Gmail opens a compose link with the reviewed recipients and message', async () => {
 const draft = {...generated, to:'vendor+bills@example.invalid', bcc:'records@example.invalid; audit@example.invalid'};
 const {container,close}=await signedInApp((url, options) => url.includes('/email-drafts/generate/')
  ? Promise.resolve({ok:true,json:async()=>draft}) : responses(url, options));
 try {
  await act(async()=>button(container,'Allotments').click());
  await act(async()=>button(container,'Prepare Gmail').click());
  await act(async()=>button(container,'Generate Draft').click());
  expect(container.querySelector('#draft-bcc').value).toBe(draft.bcc);
  act(()=>fillInput(container.querySelector('#draft-body'),'Signed bill & details\nLine two'));
  const link = container.querySelector('.gmail-compose');
  const gmail = new URL(link.href);
  const mailto = new URL(gmail.searchParams.get('url'));
  expect(gmail.origin).toBe('https://mail.google.com');
  expect(link.target).toBe('_blank');
  expect(decodeURIComponent(mailto.pathname)).toBe(draft.to);
  expect(Object.fromEntries(mailto.searchParams)).toEqual({cc:draft.cc, bcc:'records@example.invalid,audit@example.invalid',
   subject:draft.subject, body:'Signed bill & details\r\nLine two'});
 } finally { close(); }
});
function responses(url,options) {
 if(url.includes("/email-templates/"))return Promise.resolve({ok:true,json:async()=>[{id:1,name:"Invoice covering letter",subject:"Invoice for {allottee_name}",body:"Dear {allottee_name}, {bill_details}"}]});
 if(url.includes("/email-drafts/generate/"))return Promise.resolve({ok:true,json:async()=>generated});
}
test("saved template merges into a temporary editable email with copy fallback",async()=>{
 const {container,close}=await signedInApp(responses);
 await act(async()=>button(container,"Allotments").click());
 await act(async()=>button(container,"Prepare Gmail").click());
 expect(container.textContent).toContain("{allottee_name}");
 await act(async()=>button(container,"Generate Draft").click());
 expect(container.querySelector("#draft-to").value).toBe(generated.to);
 await act(async()=>button(container,"Copy Body").click());
 expect(container.textContent).toContain("Select and copy");
 await act(async()=>fillInput(container.querySelector("#draft-subject"),"Case-specific subject"));
 expect(container.querySelector("#draft-subject").value).toBe("Case-specific subject");
 expect(button(container,"Save Draft")).toBeUndefined();
 expect(global.fetch.mock.calls.filter(([url,opts])=>opts.method&&url.includes("/email-")).map(([url])=>url)).toEqual(["/api/email-drafts/generate/"]);
 close();
});
test("navigation and regeneration confirm before discarding temporary edits",async()=>{
 const confirm=jest.spyOn(window,"confirm").mockReturnValue(false);
 const {container,close}=await signedInApp(responses);
 await act(async()=>button(container,"Allotments").click());
 await act(async()=>button(container,"Prepare Gmail").click());
 await act(async()=>button(container,"Generate Draft").click());
 await act(async()=>button(container,"Refresh from current records").click());
 expect(confirm).toHaveBeenCalled();
 await act(async()=>button(container,"Dashboard").click());
 expect(container.querySelector("#draft-body")).not.toBeNull();
 confirm.mockClear();
 await act(async()=>button(container,"Back").click());
 expect(confirm).toHaveBeenCalledWith("Discard unsaved draft edits?");
 expect(container.querySelector("#draft-body")).not.toBeNull();
 confirm.mockReturnValue(true);
 await act(async()=>button(container,"Back").click());
 expect(container.querySelector("#draft-body")).toBeNull();
 expect(button(container,"Forward").disabled).toBe(false);
 confirm.mockRestore();close();
});
test("bill loading retry preserves merged text",async()=>{
 let billCalls=0;
 const {container,close}=await signedInApp((url,options)=>{
  if(url.includes("/bills/?tenant=")){
   billCalls++;
   return billCalls===1?Promise.reject(new TypeError("Network")):Promise.resolve({ok:true,json:async()=>[sampleBill]});
  }
  return responses(url,options);
 });
 await act(async()=>button(container,"Allotments").click());
 await act(async()=>button(container,"Prepare Gmail").click());
 await act(async()=>button(container,"Retry bills").click());
 expect(billCalls).toBe(2);
 await act(async()=>button(container,"Generate Draft").click());
 expect(container.querySelector("#draft-body").value).toBe(generated.body);close();
});
test("mixed allottee bill selection is rejected before merging",async()=>{
 const {container,close}=await signedInApp((url,options)=>url.includes('/bills/')?Promise.resolve({ok:true,json:async()=>[sampleBill,{...sampleBill,id:2,tenant:2,tenant_name:'Other'}]}):responses(url,options));
 await act(async()=>button(container,'Bills').click());
 await act(async()=>container.querySelector('thead input[type="checkbox"]').click());
 await act(async()=>button(container,'Draft Email').click());
 expect(container.textContent).toContain('one allottee');
 expect(global.fetch.mock.calls.some(([url])=>url.includes('/generate/'))).toBe(false);close();
});
