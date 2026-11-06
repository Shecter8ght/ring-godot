import { clamp } from './model.mjs';
import { defaultTrackFx, defaultLimiter } from './fx-model.mjs';
import { compressionReduction } from './compressor-dsp.mjs';
const $=id=>document.getElementById(id);
const fields={
  tone:[['low','Низы',-18,18,.1,'дБ'],['mid','Середина',-18,18,.1,'дБ'],['high','Верхи',-18,18,.1,'дБ'],['frequency','Частота СЧ',200,5000,10,'Гц']],
  reverb:[['wet','Доля',0,1,.01,'%'],['decay','Хвост',.15,6,.05,'с'],['preDelay','Предзадержка',0,150,1,'мс'],['damping','Тембр',500,18000,100,'Гц'],['size','Размер',0,1,.01,'%']],
  limiter:[['drive','Усиление',0,24,.1,'дБ'],['ceiling','Потолок',-18,0,.1,'дБ'],['release','Возврат',10,600,5,'мс']],
  compressor:[['threshold','Порог',-60,0,.5,'дБ'],['ratio','Сжатие',1,20,.1,':1'],['attack','Атака',.1,100,.1,'мс'],['release','Возврат',10,1500,5,'мс'],['knee','Колено',0,24,.5,'дБ'],['makeup','Усиление',-12,24,.1,'дБ'],['mix','Доля',0,1,.01,'%']]
};
const presets={room:{enabled:true,wet:.18,decay:.55,preDelay:8,damping:7800,size:.22},hall:{enabled:true,wet:.28,decay:2.2,preDelay:25,damping:6500,size:.8},dark:{enabled:true,wet:.25,decay:1.5,preDelay:35,damping:2500,size:.6}};
const compressorPresets={voice:{enabled:true,threshold:-22,ratio:3,attack:12,release:140,knee:8,makeup:3,mix:1},dense:{enabled:true,threshold:-26,ratio:4,attack:6,release:100,knee:6,makeup:5,mix:1},punch:{enabled:true,threshold:-16,ratio:4,attack:25,release:85,knee:4,makeup:2,mix:.7}};
export class FxControls{
  constructor(state,engine,hooks){
    this.state=state;this.engine=engine;this.hooks=hooks;this.container=$('fx-content');
    this.root=document.querySelector('.eq-panel');
    $('tab-fx').insertAdjacentHTML('afterend','<button id="tab-compressor" class="eq-tab" role="tab" aria-selected="false">Компрессор</button>');
    this.root.insertAdjacentHTML('beforeend','<div id="compressor-content" class="compressor-content" hidden></div>');
    $('tab-eq').onclick=()=>this.tab(false);$('tab-fx').onclick=()=>this.tab(true);$('tab-compressor').onclick=()=>this.tab('compressor');
    this.root.addEventListener('pointerdown',event=>this.down(event));
    document.addEventListener('pointermove',event=>this.move(event));document.addEventListener('pointerup',()=>this.up());
    this.root.addEventListener('wheel',event=>this.wheel(event),{passive:false});
    this.root.addEventListener('keydown',event=>this.key(event));
    this.root.addEventListener('input',event=>{const el=event.target;if(el.matches('.knob-value')){this.hooks.beginEdit();this.assign(el,Number(el.value));}});
    this.root.addEventListener('change',event=>{
      const el=event.target;if(el.matches('.knob-value')){this.hooks.endEdit('sync',false);this.render();}
      else if(el.dataset.fxEnable){this.change(()=>{this.settings(el.dataset.fxEnable).enabled=el.checked;});}
      else if(el.id==='reverb-preset'&&presets[el.value])this.change(()=>Object.assign(this.settings('reverb'),presets[el.value]));
      else if(el.id==='compressor-preset'&&compressorPresets[el.value])this.change(()=>Object.assign(this.settings('compressor'),compressorPresets[el.value]));
    });
    this.root.addEventListener('click',event=>{const group=event.target.closest('[data-fx-reset]')?.dataset.fxReset;if(group)this.change(()=>{Object.assign(this.settings(group),group==='limiter'?defaultLimiter():defaultTrackFx()[group]);});});
    this.root.addEventListener('dblclick',event=>{const el=event.target.closest('.rotary');if(el){this.hooks.beginEdit();this.assign(el,el.dataset.group==='limiter'?defaultLimiter()[el.dataset.param]:defaultTrackFx()[el.dataset.group][el.dataset.param]);this.hooks.endEdit('sync',false);}});
  }
  track(){return this.state.project.tracks.find(track=>track.id===this.state.selectedTrackId);}
  settings(group){if(group==='limiter')return this.state.project.limiter??=defaultLimiter();const track=this.track();if(!track)return null;return(track.fx??=defaultTrackFx())[group]??=defaultTrackFx()[group];}
  tab(mode){for(const[id,on]of [['tab-eq',mode===false],['tab-fx',mode===true],['tab-compressor',mode==='compressor']]){$(id).classList.toggle('active',on);$(id).setAttribute('aria-selected',String(on));}document.querySelector('.eq-content').hidden=mode!==false;document.querySelector('.eq-actions').hidden=mode!==false;this.container.hidden=mode!==true;$('compressor-content').hidden=mode!=='compressor';if(mode!==false)this.render();}
  change(action){this.hooks.beginEdit();action();this.engine.sync();this.hooks.endEdit();}
  spec(el){return fields[el.dataset.group].find(field=>field[0]===el.dataset.param);}
  assign(el,value){
    const spec=this.spec(el),settings=this.settings(el.dataset.group);if(!settings||!Number.isFinite(value))return;
    settings[spec[0]]=Number((Math.round(clamp(value,spec[2],spec[3])/spec[4])*spec[4]).toFixed(5));this.paint(el.dataset.group,spec[0]);if(el.dataset.group==='compressor')this.curve();this.engine.sync();this.hooks.liveChange();
  }
  paint(group,param){const spec=fields[group].find(field=>field[0]===param),value=this.settings(group)[param],wrap=this.root.querySelector(`[data-knob="${group}.${param}"]`);if(!wrap)return;const el=wrap.querySelector('.rotary');el.style.setProperty('--angle',`${-135+(value-spec[2])/(spec[3]-spec[2])*270}deg`);el.setAttribute('aria-valuenow',value);el.setAttribute('aria-valuetext',`${spec[5]==='%'?Math.round(value*100):Number(value.toFixed(2))} ${spec[5]}`);const number=wrap.querySelector('input');if(document.activeElement!==number)number.value=Number(value.toFixed(2));wrap.querySelector('output').textContent=spec[5]==='%'?`${Math.round(value*100)}%`:spec[5];}
  render(){
    const track=this.track();
    this.container.innerHTML=['tone','reverb','limiter'].map(group=>{
      const disabled=group!=='limiter'&&!track,settings=group==='limiter'?this.settings(group):track?this.settings(group):defaultTrackFx()[group];
      const title={tone:'Характер звука',reverb:'Реверберация',limiter:'Мастер · лимитер'}[group];
      return `<section class="fx-card ${disabled?'unavailable':''}"><div class="fx-card-heading"><label><input type="checkbox" data-fx-enable="${group}" ${settings.enabled?'checked':''} ${disabled?'disabled':''}>${title}</label><button class="text-button" data-fx-reset="${group}" ${disabled?'disabled':''}>Сброс</button></div><div class="fx-card-note">${group==='limiter'?'Общий выход · стерео · 5 мс':track?'Выбранная дорожка':'Выберите дорожку'}${group==='reverb'?'<select id="reverb-preset" aria-label="Пресет реверберации" '+(disabled?'disabled':'')+'><option value="">Пресеты</option><option value="room">Комната</option><option value="hall">Зал</option><option value="dark">Тёмный хвост</option></select>':''}</div><div class="knob-row">${fields[group].map(([key,label,min,max,step,unit])=>`<div class="knob" data-knob="${group}.${key}"><button type="button" role="slider" class="rotary" data-group="${group}" data-param="${key}" aria-label="${title}: ${label}" aria-valuemin="${min}" aria-valuemax="${max}" ${disabled?'disabled':''}><i></i></button><label>${label}</label><div><input class="knob-value" type="number" data-group="${group}" data-param="${key}" min="${min}" max="${max}" step="${step}" aria-label="${title}: ${label}, число" ${disabled?'disabled':''}><output>${unit}</output></div></div>`).join('')}</div><div class="fx-card-bottom">${group==='tone'?'НЧ 120 Гц · СЧ с широкой полосой · ВЧ 6 кГц':group==='reverb'?'Доля и тембр меняются во время прослушивания':'Снижение уровня <strong id="limiter-reduction">0.0 дБ</strong>'}</div></section>`;
    }).join('');
    this.renderCompressor();
    for(const group of Object.keys(fields))if(group==='limiter'||track)for(const[key]of fields[group])this.paint(group,key);
  }
  renderCompressor(){const disabled=!this.track(),settings=this.settings('compressor')||defaultTrackFx().compressor;
    $('compressor-content').innerHTML=`<section class="fx-card ${disabled?'unavailable':''}"><div class="fx-card-heading"><label><input type="checkbox" data-fx-enable="compressor" ${settings.enabled?'checked':''} ${disabled?'disabled':''}>Компрессор дорожки</label><select id="compressor-preset" aria-label="Пресет компрессора" ${disabled?'disabled':''}><option value="">Пресеты</option><option value="voice">Ровный голос</option><option value="dense">Плотный голос</option><option value="punch">Сохранить удар</option></select><button class="text-button" data-fx-reset="compressor" ${disabled?'disabled':''}>Сброс</button></div><div class="fx-card-note">Выравнивайте громкие и тихие участки · «Атака» оставляет начало удара · «Доля» смешивает с исходником</div><div class="knob-row">${fields.compressor.map(([key,label,min,max,step,unit])=>`<div class="knob" data-knob="compressor.${key}"><button type="button" class="rotary" role="slider" data-group="compressor" data-param="${key}" aria-label="Компрессор: ${label}" aria-valuemin="${min}" aria-valuemax="${max}" ${disabled?'disabled':''}><i></i></button><label>${label}</label><div><input class="knob-value" type="number" data-group="compressor" data-param="${key}" min="${min}" max="${max}" step="${step}" aria-label="Компрессор: ${label}, число" ${disabled?'disabled':''}><output>${unit}</output></div></div>`).join('')}</div><div class="fx-card-bottom">RMS · связанные стереоканалы · без дополнительной задержки <span>Сжатие <strong id="compressor-reduction">0.0 дБ</strong></span></div></section><section class="compressor-curve"><div>ВХОД → ВЫХОД <span>дБ</span></div><svg viewBox="0 0 300 140" role="img" aria-label="Характеристика компрессора"><path d="M20 120H280M20 120V12M20 84H280M20 48H280M85 12V120M150 12V120M215 12V120" stroke="#33445e" fill="none"/><path d="M20 120L280 30" stroke="#68809c" stroke-dasharray="4 4"/><polyline id="compressor-curve-line" fill="none" stroke="#edb27f" stroke-width="2"/><text x="20" y="137">−60</text><text x="265" y="137">0</text></svg><p>Более высокое сжатие выравнивает голос. Для выстрела оставьте более медленную атаку.</p></section>`;
    this.curve();
  }
  curve(){const settings=this.settings('compressor')||defaultTrackFx().compressor,points=[];for(let db=-60;db<=0;db+=.5){const reduction=settings.enabled?compressionReduction(db,settings.threshold,settings.ratio,settings.knee):0,wet=10**(((settings.enabled?settings.makeup:0)-reduction)/20),mix=settings.enabled?settings.mix:0,out=db+20*Math.log10(1-mix+mix*wet);points.push(`${20+(db+60)/60*260},${120-Math.min(72,Math.max(0,out+60))/72*108}`);}const line=$('compressor-curve-line');if(line)line.setAttribute('points',points.join(' '));}
  down(event){const el=event.target.closest('.rotary');if(!el||el.disabled||event.button!==0)return;event.preventDefault();this.hooks.beginEdit();this.drag={el,y:event.clientY,value:this.settings(el.dataset.group)[el.dataset.param]};el.setPointerCapture(event.pointerId);el.focus();}
  move(event){if(!this.drag)return;const{el,y,value}=this.drag,spec=this.spec(el);this.assign(el,value+(y-event.clientY)*(spec[3]-spec[2])/(event.shiftKey?1500:220));}
  up(){if(this.drag){this.drag=null;this.hooks.endEdit('sync',false);}}
  wheel(event){const el=event.target.closest('.rotary');if(!el||el.disabled)return;event.preventDefault();this.hooks.beginEdit();const spec=this.spec(el);this.assign(el,this.settings(el.dataset.group)[el.dataset.param]+(event.deltaY<0?1:-1)*spec[4]*(event.shiftKey?1:5));clearTimeout(this.wheelTimer);this.wheelTimer=setTimeout(()=>this.hooks.endEdit('sync',false),180);}
  key(event){const el=event.target.closest('.rotary');if(!el||el.disabled||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();this.hooks.beginEdit();const spec=this.spec(el),value=event.key==='Home'?spec[2]:event.key==='End'?spec[3]:this.settings(el.dataset.group)[el.dataset.param]+(['ArrowUp','ArrowRight'].includes(event.key)?1:-1)*spec[4];this.assign(el,value);this.hooks.endEdit('sync',false);}
  meter(){const el=$('limiter-reduction');if(el)el.textContent=`${(this.engine.limiter?.state.reduction||0).toFixed(1)} дБ`;const comp=$('compressor-reduction');if(comp)comp.textContent=`${(this.engine.graphs.get(this.state.selectedTrackId)?.effects.compressor.state.reduction||0).toFixed(1)} дБ`;}
}
