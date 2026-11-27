import { act, signedInApp, fillInput, sampleTenant, sampleBill } from "../../test-support/app";
const button=(container,text)=>[...container.querySelectorAll("button")].find(item=>item.textContent===text);
const first={...sampleTenant,name:"Same Person",allotment_description:"Shop 12",display_name:"Same Person — Shop 12"};
const second={...first,id:2,allotment_description:"Shop 34",display_name:"Same Person — Shop 34"};
const override=(url)=>url.includes('/tenants/')?Promise.resolve({ok:true,json:async()=>[first,second]}):url.includes('/bills/')?Promise.resolve({ok:true,json:async()=>[{...sampleBill,tenant_name:'Same Person',tenant_display_name:first.display_name}]}):null;
test('allottee descriptions distinguish names and can be searched',async()=>{
 const {container,close}=await signedInApp(override);
 await act(async()=>button(container,'Allotments').click());
 expect(container.querySelector('tbody').textContent).toContain(first.display_name);
 expect(container.querySelector('tbody').textContent).toContain(second.display_name);
 await act(async()=>fillInput(container.querySelector('#tenants-search'),'Shop 34'));
 expect(container.querySelectorAll('tbody tr')).toHaveLength(1);close();
});
test('description can be edited and bill selection shows the distinction',async()=>{
 const {container,close}=await signedInApp(override);
 await act(async()=>button(container,'Allotments').click());
 await act(async()=>button(container,'Edit').click());
 expect(container.querySelector('#tenantform-description').value).toBe('Shop 12');
 await act(async()=>button(container,'Cancel').click());
 await act(async()=>button(container,'Bills').click());
 expect(container.querySelector('#bills-tenant').textContent).toContain(first.display_name);
 expect(container.querySelector('#bills-tenant').textContent).toContain(second.display_name);
 expect(container.querySelector('tbody').textContent).toContain(first.display_name);close();
});
