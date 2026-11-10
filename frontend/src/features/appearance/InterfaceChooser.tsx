import {useAppearance} from "./AppearanceProvider";
import {resolveInterface,type InterfaceStyle} from "./model";
import {spaceInterfaces} from "./interfaceCatalog";
import {ModuleSigil} from "./ModuleSigil";

export function InterfaceChooser() {
 const a=useAppearance(),selected=resolveInterface(a.personal.preferences.interface),disabled=!a.ready||a.busy;
 return <section className="interface-choice" aria-labelledby="interface-heading"><h4 id="interface-heading">Interface</h4>
  <p className="muted">Six workspaces for the same capsuleer. Choose a layout, or apply one of the four space editions with its own colors.</p>
  <label>Layout only<select aria-label="EQM interface" value={selected} disabled={disabled} onChange={event=>void a.save({interface:event.target.value as InterfaceStyle})}><option value="classic">EQM-Classic</option><option value="command_desk">Command Desk</option>{Object.entries(spaceInterfaces).map(([id,choice])=><option key={id} value={id}>{choice.name}</option>)}</select></label>
  <div className="interface-editions">{Object.entries(spaceInterfaces).map(([id,choice],index)=><article key={id} className={`interface-edition edition-${id.replace(/_/g,"-")}`} data-selected={selected===id}>
    <div className="edition-preview" aria-hidden="true" style={{background:choice.theme.background,color:choice.theme.accent,borderColor:choice.theme.border}}>
      <svg viewBox="0 0 180 86" fill="none" stroke="currentColor" strokeWidth="1.2">{index===0?<><ellipse cx="90" cy="43" rx="72" ry="31"/><circle cx="90" cy="43" r="18"/><path d="M20 12h140M20 74h140M45 12v12m90 38v12"/></>:index===1?<><path d="M25 73V33a20 20 0 0 1 40 0v40zm55 0V26a20 20 0 0 1 40 0v47zm55 0V33a15 15 0 0 1 30 0v40z"/><path d="M35 42h20m35-5h20m32 5h16"/></>:index===2?<><path d="m28 45 19-22 28 30 33-30 38 27M108 23v40M12 72h156"/><path d="m47 17 6 6-6 6-6-6zm61 0 6 6-6 6-6-6zm38 27 6 6-6 6-6-6z"/></>:<><path d="M18 17h144v52H18zM18 30h144M45 30v39M56 40h90M56 50h72M56 60h54"/><path d="M25 22h12m-12 17h12m-12 10h12m-12 10h12"/></>}</svg>
      <div className="edition-samples"><ModuleSigil module="navigation"/><ModuleSigil module="industry"/><ModuleSigil module="intel_reports"/></div>
    </div>
    <div className="edition-copy"><h5>{choice.name}{selected===id&&<span className="edition-selected">Selected</span>}</h5><p>{choice.description}</p><small>{choice.layout} · {choice.geometry}</small><button type="button" disabled={disabled} aria-pressed={selected===id} aria-label={`Apply ${choice.name} layout and colors`} onClick={()=>void a.save({interface:id as InterfaceStyle,theme:choice.theme})}>Apply layout & colors</button></div>
  </article>)}</div>
  <p className="muted">Layout only keeps your palette. Apply layout & colors uses the edition palette. Your banner, shortcuts and panel positions stay saved; switch back at any time.</p>
 </section>;
}
