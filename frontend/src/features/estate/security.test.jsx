import { act, fillInput, signedInApp, createRoot } from '../../test-support/app';
import { SecurityDecisionForm } from './EstateSecurity';
import API from '../../api';

const reply=data=>Promise.resolve({ok:true,json:async()=>data});
const button=(container,label)=>[...container.querySelectorAll('button')].find(node=>node.textContent.trim()===label);
const account={id:91,shop_code:'A101',tenant:1,required_amount:'5500.00',held:'1000.00',received:'1000.00',refunded:'0.00',applied:'0.00',forfeited:'0.00',refund_review_due:'2027-03-31',movements:[],clearance_issues:['Handover pending']};
test('staff record actual deposit receipts against the original award and cannot approve decisions',async()=>{
  const fixture=(url,options)=>url.includes('/estate-security/')?reply(account):url.includes('/allotments/')?reply([{id:11,shop:1,shop_code:'A101',tenant:1,original_award_id:91,award_reference:'Renewal'}]):url.includes('/shops/')?reply([{id:1,code:'A101',name:'Shop'}]):url.includes('/security-movements/')?reply({id:1}):null;
  const {container,close}=await signedInApp(fixture);
  try{
    await act(async()=>button(container,'Allotments').click());await act(async()=>button(container,'Details').click());
    expect(button(container,'Review security requirement')).toBeUndefined();
    await act(async()=>button(container,'Record deposit receipt').click());
    for(const [id,value] of [['security-receipt-amount','400'],['security-receipt-reference','DD-42'],['security-receipt-reason','Actual security receipt evidence']]) await act(async()=>fillInput(container.querySelector(`#${id}`),value));
    await act(async()=>container.querySelector('form[aria-label="Security deposit receipt"]').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    const request=global.fetch.mock.calls.find(([url,options])=>url.endsWith('/security-movements/')&&options.method==='POST');
    expect(JSON.parse(request[1].body)).toMatchObject({original_award:91,amount:'400',reference:'DD-42'});
  }finally{close();}
});

test('security confirmation requires the reviewed values and changing them invalidates it',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const post=jest.spyOn(API,'post').mockResolvedValue({before:account,after:{...account,required_amount:'5400.00'},confirmation:'signed-security'});
  const container=document.createElement('div');document.body.appendChild(container);const root=createRoot(container);const save=jest.fn();
  try{
    await act(async()=>root.render(<SecurityDecisionForm account={account} action="requirement" chain={[]} bills={[]} onSave={save} onClose={()=>{}} />));
    for(const [id,value] of [['security-initial-rent','1800'],['security-decision-reference','Approval-1'],['security-decision-reason','Reviewed initial rent basis']]) await act(async()=>fillInput(container.querySelector(`#${id}`),value));
    expect(button(container,'Confirm reviewed security decision')).toBeUndefined();
    await act(async()=>container.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    await act(async()=>button(container,'Confirm reviewed security decision').click());
    expect(save).toHaveBeenCalledWith({confirmation:'signed-security'});
    await act(async()=>fillInput(container.querySelector('#security-initial-rent'),'1900'));
    expect(button(container,'Confirm reviewed security decision')).toBeUndefined();
  }finally{act(()=>root.unmount());container.remove();post.mockRestore();}
});

test('bill applications load current eligible bills even when the main bill list was not visited',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const get=jest.spyOn(API,'getAll').mockResolvedValue([{id:8,allotment:11,shop_code:'A101',invoice_no:'CURRENT-8',balance_due:'400',penalty:'0'}]);
  const container=document.createElement('div');document.body.appendChild(container);const root=createRoot(container);
  try{
    await act(async()=>root.render(<SecurityDecisionForm account={account} action="apply_bill" chain={[{id:11}]} bills={[]} onSave={()=>{}} onClose={()=>{}} />));
    expect(get).toHaveBeenCalledWith('/bills/?tenant=1');
    expect(container.querySelector('select').textContent).toContain('CURRENT-8');
  }finally{act(()=>root.unmount());container.remove();get.mockRestore();}
});
