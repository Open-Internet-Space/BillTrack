import { act, fillInput, signedInApp } from '../../test-support/app';
import { createRoot } from 'react-dom/client';
import { ChargeDecisionForm, ChargePaymentForm } from './EstateCharges';
import API from '../../api';

const reply = data => Promise.resolve({ok:true,json:async()=>data});
const term = {id:1,shop:1,shop_code:'A101',tenant:1,tenant_name:'Tester',award_reference:'Award',notice_governed:true,extension_number:0,renewal_fee_settled:false};
const button = (container, text) => [...container.querySelectorAll('button')].find(node=>node.textContent.trim()===text);
const fixture = (url, options) => url.includes('/allotments/') ? reply([term]) : url.includes('/shops/') ? reply([{id:1,code:'A101',name:'Shop',active:true}]) : url.includes('/estate-charges/') ? reply(options.method==='POST'?{id:2}:[]) : null;

test('renewal waits for its fee and assessment requires explicit tax evidence', async()=>{
  const {container,close}=await signedInApp(fixture);
  try {
    await act(async()=>button(container,'Allotments').click());
    await act(async()=>button(container,'Details').click());
    expect(button(container,'Record renewal').disabled).toBe(true);
    await act(async()=>button(container,'Assess extension fee').click());
    expect(container.querySelector('#charge-net').value).toBe('1000');
    expect(container.querySelector('#charge-tax').value).toBe('');
    expect(container.querySelector('#charge-tax').required).toBe(true);
    for (const [id,value] of [['charge-tax','0'],['charge-description','Extension approval fee'],['charge-authority','Memo 1']]) {
      await act(async()=>fillInput(container.querySelector(`#${id}`),value));
    }
    await act(async()=>container.querySelector('form[aria-label="Charge assessment"]').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    const request=global.fetch.mock.calls.find(([url,options])=>url.endsWith('/estate-charges/')&&options.method==='POST');
    expect(JSON.parse(request[1].body)).toMatchObject({allotment:1,kind:'extension_fee',net_amount:'1000',tax_amount:'0',authority_reference:'Memo 1'});
  } finally {close();}
});

test('charge receipt records actual evidence without a settlement source selector',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const container=document.createElement('div');document.body.appendChild(container);
  const root=createRoot(container);const save=jest.fn();
  try {
    await act(async()=>root.render(<ChargePaymentForm charge={{id:3,shop_code:'A101',balance_due:'1000',assessed_on:'2026-01-01'}} onSave={save} onClose={()=>{}} />));
    expect(container.querySelector('#charge-payment-amount').value).toBe('');
    for(const [id,value] of [['charge-payment-amount','400'],['charge-payment-reference','DD-1']]) await act(async()=>fillInput(container.querySelector(`#${id}`),value));
    await act(async()=>container.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({charge:3,amount:'400',receipt_reference:'DD-1'}));
    expect(save.mock.calls[0][0].source).toBeUndefined();
  }finally{act(()=>root.unmount());container.remove();}
});

test('financial decision requires a preview and invalidates it after input changes',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const post=jest.spyOn(API,'post').mockResolvedValue({before:{gross_amount:'1000',waiver_amount:'0',balance_due:'600'},after:{gross_amount:'1000',waiver_amount:'200',balance_due:'400'},confirmation:'signed-review'});
  const container=document.createElement('div');document.body.appendChild(container);const root=createRoot(container);const save=jest.fn();
  try {
    await act(async()=>root.render(<ChargeDecisionForm charge={{id:3,waiver_amount:'0'}} action="waiver" onSave={save} onClose={()=>{}} />));
    expect(button(container,'Confirm reviewed decision')).toBeUndefined();
    for(const [id,value] of [['decision-waiver_amount','200'],['decision-reference','Approval-1'],['decision-reason','Approved remission']]) await act(async()=>fillInput(container.querySelector(`#${id}`),value));
    await act(async()=>container.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    expect(post).toHaveBeenCalledWith('/estate-charges/3/decision-preview/',expect.objectContaining({waiver_amount:'200',action:'waiver'}));
    await act(async()=>button(container,'Confirm reviewed decision').click());
    expect(save).toHaveBeenCalledWith({confirmation:'signed-review'});
    await act(async()=>fillInput(container.querySelector('#decision-waiver_amount'),'100'));
    expect(button(container,'Confirm reviewed decision')).toBeUndefined();
  }finally{act(()=>root.unmount());container.remove();post.mockRestore();}
});
