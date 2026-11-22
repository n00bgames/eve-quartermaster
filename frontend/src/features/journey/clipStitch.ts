import {Input,BlobSource,MP4,EncodedPacketSink,EncodedVideoPacketSource,EncodedAudioPacketSource,Output,Mp4OutputFormat,StreamTarget,type StreamTargetChunk} from 'mediabunny';

export {sortClips} from './clipOrder.ts';
function description(value:AllowSharedBufferSource|undefined){
 if(!value)return '';
 const bytes=ArrayBuffer.isView(value)?new Uint8Array(value.buffer,value.byteOffset,value.byteLength):new Uint8Array(value);
 return Array.from(bytes).map(n=>n.toString(16).padStart(2,'0')).join('');
}
export function configKey(config:VideoDecoderConfig|AudioDecoderConfig|null){
 if(!config)throw new Error('A clip is missing decoder configuration.');
 return JSON.stringify({...config,description:description(config.description)});
}
const check=(signal:AbortSignal)=>{if(signal.aborted)throw new DOMException('Stitch cancelled','AbortError');};
async function open(file:File){
 const input=new Input({source:new BlobSource(file,{maxCacheSize:2*1024*1024}),formats:[MP4]});
 try{
  const videos=await input.getVideoTracks(),audios=await input.getAudioTracks();
  if(videos.length!==1||audios.length>1)throw new Error(`${file.name}: use EQM clips with one video and at most one audio track.`);
  const video=videos[0],audio=audios[0]??null,videoConfig=await video.getDecoderConfig(),audioConfig=audio?await audio.getDecoderConfig():null;
  if(await video.getCodec()!=='avc'||await video.getCodedWidth()!==1920||await video.getCodedHeight()!==1080)throw new Error(`${file.name}: expected a 1920 × 1080 H.264 Journey MP4.`);
  if(audio&&await audio.getCodec()!=='aac')throw new Error(`${file.name}: only AAC Journey audio is supported.`);
  const first=await new EncodedPacketSink(video).getFirstPacket();
  if(!first||first.type!=='key')throw new Error(`${file.name}: video must start with a keyframe.`);
  return {input,video,audio,videoConfig:videoConfig!,audioConfig,first:first.timestamp};
 }catch(error){input.dispose();throw error;}
}
export async function validateClips(files:File[],signal:AbortSignal){
 if(files.length<2)throw new Error('Select at least two Journey MP4 clips.');
 const signatures:string[]=[];
 for(const file of files){
  check(signal);const clip=await open(file);
  try{signatures.push(configKey(clip.videoConfig)+'|'+(clip.audio?configKey(clip.audioConfig):'silent'));}
  finally{clip.input.dispose();}
 }
 if(signatures.some(key=>key!==signatures[0]))throw new Error('These clips have different video or audio settings. Export matching clips (all with music, or all silent); no file was written.');
}

/** Remux compatible packets; do not decode frames or accumulate a combined Blob. */
export async function stitchClips(files:File[],stream:FileSystemWritableFileStream,signal:AbortSignal,progress:(done:number,total:number)=>void){
 let output:Output<Mp4OutputFormat,StreamTarget>|undefined,seconds=0,videoSequence=0,audioSequence=0;
 let videoSource:EncodedVideoPacketSource|undefined,audioSource:EncodedAudioPacketSource|undefined;
 try{
  for(let i=0;i<files.length;i++){
   check(signal);const clip=await open(files[i]);
   try{
    if(!output){
     // Keep the actual file transaction under our control: cancelling the muxer
     // closes its target, but must abort rather than commit a partial user file.
     const sink=new WritableStream<StreamTargetChunk>({write:chunk=>stream.write(chunk)});
     output=new Output({format:new Mp4OutputFormat({fastStart:'fragmented'}),target:new StreamTarget(sink,{chunked:true,chunkSize:2*1024*1024})});
     videoSource=new EncodedVideoPacketSource('avc');output.addVideoTrack(videoSource);
     if(clip.audio){audioSource=new EncodedAudioPacketSource('aac');output.addAudioTrack(audioSource);}
     output.setMetadataTags({title:'EQM · combined Journey clips',artist:'EVE Quartermaster'});await output.start();
    }
    const video=new EncodedPacketSink(clip.video).packets(),audio=clip.audio?new EncodedPacketSink(clip.audio).packets():null;
    let v=await video.next(),a=audio?await audio.next():null,end=0,firstVideo=true,firstAudio=true;
    while(!v.done||(a&&!a.done)){
     check(signal);
     const useVideo=!v.done&&(!a||a.done||v.value.timestamp<=a.value.timestamp),packet=useVideo?v.value:a!.value;
     if(!packet)throw new Error('Missing encoded packet.');
     const local=packet.timestamp-clip.first;
     end=Math.max(end,local+packet.duration);
     // Encoder priming can have negative timestamps. Drop complete pre-roll
     // packets so adjacent clips do not overlap their decode timestamps.
     if(local>=-0.000001){
      const shifted=packet.clone({timestamp:Math.max(0,local)+seconds,sequenceNumber:useVideo?videoSequence++:audioSequence++});
      if(useVideo){await videoSource!.add(shifted,firstVideo?{decoderConfig:clip.videoConfig}:undefined);firstVideo=false;}
      else{await audioSource!.add(shifted,firstAudio?{decoderConfig:clip.audioConfig!}:undefined);firstAudio=false;}
     }
     if(useVideo)v=await video.next();else a=await audio!.next();
    }
    seconds+=end;progress(i+1,files.length);
   }finally{clip.input.dispose();}
  }
  check(signal);videoSource!.close();audioSource?.close();await output!.finalize();check(signal);await stream.close();
  return seconds;
 }catch(error){try{await output?.cancel();}catch{}try{await stream.abort();}catch{}throw error;}
}
