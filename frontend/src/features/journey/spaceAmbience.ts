/** Original procedural score: slow detuned pads and sparse bell tones. No
 * recordings, third-party music, network fetches, or full-track PCM buffers. */
export function ambienceSamples(start:number,frames:number,sampleRate:number,duration:number,volume:number):Float32Array{
 const data=new Float32Array(frames),gain=Math.max(0,Math.min(.3,volume));
 for(let i=0;i<frames;i++){
  const t=start+i/sampleRate,fade=Math.max(0,Math.min(1,t/2,(duration-t)/2));
  const pad=[55,82.4069,110,164.8138].reduce((n,f,j)=>n+Math.sin(2*Math.PI*f*t+.13*Math.sin(t*.17+j))*(.035+.015*Math.sin(t*.11+j)),0);
  const phrase=Math.floor(t/6),age=t%6,bell=Math.sin(2*Math.PI*[220,329.6276,440,293.6648][phrase%4]*age)*Math.exp(-age*1.4)*.12*Math.min(1,age*20);
  data[i]=(pad+bell)*gain*fade;
 }
 return data;
}
