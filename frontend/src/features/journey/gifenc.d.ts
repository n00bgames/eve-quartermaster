declare module 'gifenc' {
 export function applyPalette(rgba:Uint8ClampedArray,palette:number[][],format?:string):Uint8Array;
 export function GIFEncoder():{writeFrame(data:Uint8Array,width:number,height:number,options:{palette:number[][];delay:number;repeat:number}):void;finish():void;bytesView():Uint8Array};
}
