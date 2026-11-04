import {EXPORT_WIDTH,EXPORT_HEIGHT,MAX_EXPORT_BYTES,type ExportRequest,type ExportMessage} from './exportModel';
import {renderExportFrame} from './exportRenderer';

const MAX_BYTES=MAX_EXPORT_BYTES;
class SizeLimitError extends Error {}
const send=(message:ExportMessage,transfer:Transferable[]=[])=>postMessage(message,{transfer});
const palette:number[][]=[];
for(let r=0;r<6;r++)for(let g=0;g<6;g++)for(let b=0;b<6;b++)palette.push([r*51,g*51,b*51]);
for(const hex of ['060e18','0d1b29','294359','e4f2fa','8dabbc','55c8ef','203447','ffffff','ff7777','64e2ad','21394a','102236','20364a','a0c4d8','b0d9ed','80dbfa','e0e8ef','204b66','30556b','40738c','508ca5','102e46','30506a','203040'])palette.push([0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)));
for(let n=0;n<16;n++){const v=Math.round(n*255/15);palette.push([v,v,v]);}

onmessage=async(event:MessageEvent<ExportRequest>)=>{
 const {plan,format,logo,version}=event.data;
 let cancel:(()=>Promise<void>)|undefined;
 try{
  const canvas=new OffscreenCanvas(EXPORT_WIDTH,EXPORT_HEIGHT),ctx=canvas.getContext('2d',{alpha:false,willReadFrequently:format==='gif'});
  if(!ctx)throw new Error('Canvas rendering is unavailable in this browser.');
  const fps=format==='gif'?10:30,frames=Math.ceil(plan.duration*fps);
  let add:(i:number)=>Promise<void>,finish:()=>Promise<ArrayBuffer>;
  if(format==='gif'){
   const {GIFEncoder,applyPalette}=await import('gifenc'),encoder=GIFEncoder();
   add=async i=>{const rgba=ctx.getImageData(0,0,EXPORT_WIDTH,EXPORT_HEIGHT).data;encoder.writeFrame(applyPalette(rgba,palette,'rgb444'),EXPORT_WIDTH,EXPORT_HEIGHT,{palette,delay:100,repeat:0});if(encoder.bytesView().byteLength>MAX_BYTES)throw new SizeLimitError('GIF exceeds 128 MiB. Choose a shorter visit range.');};
   finish=async()=>{encoder.finish();return encoder.bytesView().slice().buffer as ArrayBuffer;};
  }else{
   const {Output,Mp4OutputFormat,BufferTarget,CanvasSource,Quality,canEncodeVideo}=await import('mediabunny');
   const quality=new Quality({bitrate:6_000_000});
   if(!await canEncodeVideo('avc',{width:EXPORT_WIDTH,height:EXPORT_HEIGHT,quality,frameRate:fps}))throw new Error('1080p H.264 encoding is unavailable. Try current desktop Chrome or Edge, or export GIF.');
   const target=new BufferTarget(),output=new Output({format:new Mp4OutputFormat({fastStart:false}),target});
   cancel=()=>output.cancel();
   target.on('write',({end})=>{if(end>MAX_BYTES)throw new SizeLimitError('MP4 exceeds 128 MiB. Choose a shorter visit range.');});
   const source=new CanvasSource(canvas,{codec:'avc',quality});output.addVideoTrack(source,{frameRate:fps});
   output.setMetadataTags({title:`My Journey · ${plan.history.character.name}`,artist:`EVE Quartermaster ${version}`,date:new Date(plan.exportedAt)});
   await output.start();
   add=i=>source.add(i/fps,Math.min(1/fps,plan.duration-i/fps));
   finish=async()=>{source.close();await output.finalize();if(!target.buffer)throw new Error('No encoded MP4 data was produced.');return target.buffer;};
  }
  for(let i=0;i<frames;i++){
   renderExportFrame(ctx,plan,i/fps,logo,version);await add(i);
   if(i%fps===0)send({type:'progress',progress:i/frames});
  }
  const buffer=await finish();if(buffer.byteLength>MAX_BYTES)throw new SizeLimitError('Export exceeds 128 MiB. Choose a shorter visit range.');
  send({type:'done',buffer,mime:format==='gif'?'image/gif':'video/mp4'},[buffer]);
 }catch(error){try{await cancel?.();}catch{}send({type:'error',message:error instanceof Error?error.message:String(error),code:error instanceof SizeLimitError?'size_limit':undefined});}
 finally{logo.close();}
};
