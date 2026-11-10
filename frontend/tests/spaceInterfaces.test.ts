import test from "node:test";
import assert from "node:assert/strict";
import {resolveInterface,defaultNavigation,navigationWithDefaults,themeError} from "../src/features/appearance/model.ts";
import {spaceInterfaces,interfaceShellClass,frontierNavigationGroups} from "../src/features/appearance/interfaceCatalog.ts";

test("four distinct editions resolve and expose readable default palettes",()=>{
  assert.equal(Object.keys(spaceInterfaces).length,4);
  const layouts=new Set(),classes=new Set(),palettes=new Set();
  for(const [id,choice] of Object.entries(spaceInterfaces)) {
    assert.equal(resolveInterface(id),id);assert.equal(themeError(choice.theme),"");
    layouts.add(choice.layout);classes.add(interfaceShellClass(resolveInterface(id)));palettes.add(JSON.stringify(choice.theme));
  }
  assert.equal(layouts.size,4);assert.equal(classes.size,4);assert.equal(palettes.size,4);
  assert.equal(interfaceShellClass("classic"),"");assert.equal(interfaceShellClass("command_desk")," command-desk-shell");
});
test("old and unknown preferences continue to resolve safely",()=>{
  for(const value of [null,undefined,"unknown",{},2,true,"Orbital Ring"])assert.equal(resolveInterface(value),"classic");
  assert.equal(resolveInterface("classic"),"classic");assert.equal(resolveInterface("command_desk"),"command_desk");
});
test("frontier separates Profile and Administration without changing saved shortcuts or losing modules",()=>{
  const saved=navigationWithDefaults([{id:"quick",name:"Quicklaunch",modules:["profile","industry","settings"]},...defaultNavigation]);
  const before=JSON.stringify(saved),groups=frontierNavigationGroups(saved);
  assert.equal(JSON.stringify(saved),before);
  assert.deepEqual(groups.find(g=>g.id==="frontier-profile")?.modules,["profile"]);
  assert.deepEqual(groups.find(g=>g.id==="frontier-administration")?.modules,["settings","audit"]);
  assert.deepEqual(new Set(groups.flatMap(g=>g.modules)),new Set(saved.flatMap(g=>g.modules)));
  assert.equal(groups.flatMap(g=>g.modules).filter(m=>m==="profile").length,1);
  assert.equal(groups.flatMap(g=>g.modules).filter(m=>m==="industry").length,2);
});
