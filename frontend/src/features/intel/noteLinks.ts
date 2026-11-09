export const noteSearchLink = (text:string) => `#intel-notes?q=${encodeURIComponent(text)}`;
export function noteQueryFromHash(hash:string):string|null {
  if(!hash.startsWith("#intel-notes"))return null;
  return new URLSearchParams(hash.split("?")[1]??"").get("q")??"";
}
export type NotePreview={id:number;body:string;truncated:boolean;is_private:boolean;author:string;created_at:string};
export type CharacterNotes={subject_id:number;notes:NotePreview[];total:number};
export type ScanNotes=Record<string,CharacterNotes>;
