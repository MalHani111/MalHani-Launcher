const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'../launcher/startup-service.js'),'utf8');
function setup(error){let tasks=[],calls=[],intervals=0;const context={module:{exports:{}},console:{log(){}},setTimeout(fn){tasks.push(fn);return tasks.length},clearTimeout(){tasks=[]},setInterval(){intervals++;return 1},clearInterval(){intervals--},tizen:{application:{launch(id,ok,fail){calls.push(id);if(error)fail({name:error});else ok()}}}};vm.runInNewContext(source,context);return {life:context.module.exports,calls,tasks:()=>tasks,run(){const f=tasks.shift();if(f)f()},intervals:()=>intervals};}
let s=setup();s.life.onStart();s.life.onStart();s.life.onRequest();assert.deepEqual(s.calls,['OpenHomeTV.Launcher']);assert.equal(s.tasks().length,0);assert.equal(s.intervals(),1);s.life.onStop();assert.equal(s.intervals(),0);
s=setup('UnknownError');s.life.onStart();for(let i=0;i<30;i++)s.run();assert.equal(s.calls.length,15);assert.equal(s.tasks().length,0);
for(const error of ['SecurityError','NotFoundError']){s=setup(error);s.life.onStart();assert.equal(s.calls.length,1);assert.equal(s.tasks().length,0);}
s=setup('UnknownError');s.life.onStart();s.life.onStop();s.run();assert.equal(s.calls.length,1);
console.log('PASS: one launch per start, bounded transient retries, no privilege/missing-app retry loop, timer cleanup and no network dependencies.');
