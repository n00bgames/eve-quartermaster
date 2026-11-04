import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,httpErrorMessage} from '../src/lib/apiErrors.ts';

test('nginx HTML is replaced with readable status messages',()=>{
 const html='<html><head><title>504 Gateway Time-out</title></head><body>nginx/1.29.8</body></html>';
 for(const status of [500,502,503,504]){const message=httpErrorMessage(status,html);assert.ok(!message.includes('<'));assert.ok(!message.includes('nginx'));}
 assert.match(httpErrorMessage(504,html),/running sync may still be active/);
 assert.equal(new ApiError(504,'Timeout').status,504);
});
test('structured authorization errors and safe busy notices remain meaningful',()=>{
 assert.equal(httpErrorMessage(409,{message:'Re-link this character',code:'consent'}),'Re-link this character');
 assert.equal(httpErrorMessage(403,'Permission required'),'Permission required');
 assert.equal(httpErrorMessage(503,'Character authorization is busy.'),'Character authorization is busy.');
});
