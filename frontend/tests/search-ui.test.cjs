"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../static/js/app.js"), "utf8");
function actual(start, end) { return source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start))); }
function controls() {
  const c = {};
  for (const name of ["queryInput", "sportSelect", "venueSelect", "venueTypeSelect", "dateInput", "timeFromInput", "timeToInput", "stateSelect"]) c[name] = {value: ""};
  c.stateSelect.value = "Open";
  return c;
}
function node() { return {hidden: false, children: [], textContent: "", append(...v) {this.children.push(...v);}, replaceChildren(...v) {this.children = v;}}; }

test("UT-US2-UI-01: actual search params retain sport, venue, type and Bangkok window separately", () => {
  const c = {...controls(), URLSearchParams};
  c.queryInput.value = "  Badminton  "; c.sportSelect.value = "7"; c.venueSelect.value = "8";
  c.venueTypeSelect.value = "Indoor"; c.dateInput.value = "2026-11-19";
  c.timeFromInput.value = "09:00"; c.timeToInput.value = "11:00";
  vm.createContext(c);
  vm.runInContext(actual("function activeFilters()", "function renderChips()") + actual("function searchParams(", "function updateSearchUrl(") + "globalThis.params=searchParams(2)", c);
  assert.deepEqual(Object.fromEntries(c.params), {q:"Badminton",sport_id:"7",venue_id:"8",venue_type:"Indoor",starts_from:"2026-11-19T09:00:00+07:00",starts_to:"2026-11-19T11:00:00+07:00",page:"2"});
});

test("UT-US2-UI-02: actual reset clears form, invalidates pending request and reloads page1", () => {
  const c = controls(); const calls = [];
  for (const n of Object.values(c)) n.value = "old";
  Object.assign(c, {form:{reset(){ for (const name of Object.keys(controls())) c[name].value = name === "stateSelect" ? "Open" : ""; }},updateTimeControls(){calls.push("time");},updateVenueOptions(){calls.push("venues");},searchState:{reset(){calls.push("invalidate");}},loadSearchResults(page){calls.push(page);}});
  vm.createContext(c); vm.runInContext(actual("function clearFilters()", "const initialParams =") + "clearFilters()", c);
  for (const name of Object.keys(controls())) assert.equal(c[name].value, name === "stateSelect" ? "Open" : "");
  assert.deepEqual(calls,["time","venues","invalidate",1]);
});

function renderContext(parties) {
  const c = {loadState:"success",parties,totalResults:parties.length,currentPage:1,pageSize:20,sportNames:new Map([[7,"Badminton"]]),venueNames:new Map([[8,{name:"Court"}]]),activeFilters:()=>({state:"all"}),renderChips(){},setVisible(n,v){n.hidden=!v;},element(tag,cls,text){return Object.assign(node(),{tag,className:cls,textContent:text});},initials:()=>"H",formatDateTime:()=>"Tomorrow"};
  for (const n of ["resultHeading","resultCount","status","errorState","loginState","emptyState","resultGrid","pagination","pageLabel","previousPage","nextPage","errorMessage"]) c[n]=node();
  vm.createContext(c); vm.runInContext(actual("function renderResults()", "function searchParams("),c);
  return c;
}

test("UT-US2-UI-04: actual cards show full/started/cancelled states and navigate to Detail", () => {
  const states = ["Full","InProgress","Cancelled"];
  const c = renderContext(states.map((state,i)=>({id:i+1,state,title:state,sport_id:7,venue_id:8,host:{display_name:"Host"},member_count:2,capacity:2,remaining_slots:0})));
  vm.runInContext("renderResults()",c);
  assert.equal(c.resultGrid.children.length,3);
  c.resultGrid.children.forEach((card,i)=>{
    assert.match(card.children[0].children[1].className,new RegExp(states[i].toLowerCase()));
    const link = card.children[2].children[1];
    assert.equal(link.tag,"a"); assert.equal(link.href,`/parties/${i+1}/`);
    assert.equal(link.textContent,"ดูรายละเอียด");
  });
});

test("UT-US2-UI-04: actual empty and error states remain distinct", () => {
  const c = renderContext([]); vm.runInContext("renderResults()",c);
  assert.equal(c.emptyState.hidden,false); assert.equal(c.errorState.hidden,true);
  vm.runInContext('showError("HTTP failure")',c);
  assert.equal(c.emptyState.hidden,true); assert.equal(c.errorState.hidden,false);
  assert.equal(c.errorMessage.textContent,"HTTP failure");
});

test("UT-US2-UI-04: actual loading hides old results, empty and error until latest response", async () => {
  let complete;
  const c = {searchReady:true,loadState:"success",searchState:require("../static/js/search-request-state.js").create(),updateSearchUrl(){},searchParams:()=>new URLSearchParams({page:"1"}),pageSize:20,request:()=>new Promise(resolve=>{complete=resolve;}),setVisible(n,v){n.hidden=!v;},renderResults(){c.rendered=true;}};
  for (const n of ["status","resultGrid","emptyState","errorState","loginState","pagination"]) c[n]=node();
  vm.createContext(c); vm.runInContext(actual("async function loadSearchResults(", "function clearFilters()") + "globalThis.pending=loadSearchResults(1)",c);
  assert.equal(c.status.hidden,false); assert.match(c.status.textContent,/กำลังค้นหา/);
  for (const n of ["resultGrid","emptyState","errorState","pagination"]) assert.equal(c[n].hidden,true);
  complete({data:[],total:0,page:1}); await c.pending;
  assert.equal(c.rendered,true); assert.equal(c.loadState,"success");
});
