import fs from "fs";
import path from "path";
const source=fs.readFileSync(path.resolve(process.cwd(),'../estate_app/static/estate_app/email_template_placeholders.js'),'utf8');
function setup(){
 document.body.innerHTML='<select id="placeholder-target"><option value="id_body">Body</option><option value="id_subject">Subject</option></select><select id="placeholder-choice"><option value="allottee_name" data-description="Person name">Name</option><option value="bill_details" data-description="Selected bill amounts" data-multiline="true">Bills</option></select><button id="placeholder-insert" type="button">Insert placeholder</button><p id="placeholder-description"></p><p id="placeholder-status"></p><input id="id_subject" value="Invoice: "><textarea id="id_body">Dear vendor,</textarea>';
 window.eval(source);document.dispatchEvent(new Event('DOMContentLoaded'));
 return {body:document.getElementById('id_body'),subject:document.getElementById('id_subject'),target:document.getElementById('placeholder-target'),choice:document.getElementById('placeholder-choice'),insert:document.getElementById('placeholder-insert')};
}
afterEach(()=>{document.body.innerHTML='';});
test('inserts at caret and replaces selected text without submitting',()=>{
 const {body,choice,insert}=setup();body.focus();body.setSelectionRange(5,11);
 insert.click();expect(body.value).toBe('Dear {allottee_name},');
 expect(body.selectionStart).toBe("Dear {allottee_name}".length);
 expect(document.getElementById('placeholder-status').textContent).toContain('Save the template');
 choice.value='bill_details';choice.dispatchEvent(new Event('change'));
 expect(document.getElementById('placeholder-description').textContent).toBe('Selected bill amounts');
});
test('subject focus targets subject and disallows multiline fields',()=>{
 const {subject,body,choice,insert}=setup();subject.focus();subject.setSelectionRange(9,9);
 expect(choice.querySelector('[value="bill_details"]').disabled).toBe(true);
 insert.click();expect(subject.value).toBe('Invoice: {allottee_name}');
 expect(body.value).toBe('Dear vendor,');
});
