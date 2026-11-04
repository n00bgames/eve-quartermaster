export class ApiError extends Error {
  readonly status:number;
  constructor(status:number,message:string){super(message);this.name='ApiError';this.status=status;}
}

export function httpErrorMessage(status:number,detail:unknown):string{
  if(status===504)return 'The server timed out while responding. A running sync may still be active; check its status before starting another.';
  if(status===502)return 'The server is temporarily unavailable. Please try again shortly.';
  if(status===503)return typeof detail==='string'&&!/<(?:!doctype|html|head|body)\b/i.test(detail)?detail:'The server is busy. Please try again shortly.';
  if(typeof detail==='string'){
    if(/<(?:!doctype|html|head|body)\b/i.test(detail))return `Server request failed (${status}). Please try again shortly.`;
    return detail.trim().slice(0,1000)||`Request failed (${status}).`;
  }
  if(detail&&typeof detail==='object'){
    const data=detail as {message?:unknown;detail?:unknown};
    if(typeof data.message==='string')return data.message;
    if(data.detail!==undefined)return httpErrorMessage(status,data.detail);
    return JSON.stringify(detail);
  }
  return `Request failed (${status}).`;
}
