import {test} from 'node:test';
import assert from 'node:assert/strict';
import {clampPanel} from '../src/forge-ui/state.mjs';
test('restaura painel dentro da tela depois de trocar resolução',()=>{const p=clampPanel({x:4000,y:3000,width:1000,height:2000},800,600);assert.ok(p.x+p.width<=800);assert.ok(p.y+p.height<=600);assert.ok(p.y>=76)});
test('recupera valores inválidos salvos no navegador',()=>{const p=clampPanel({x:'oops',width:null,tab:'desconhecida'},1200,900);assert.equal(p.x,28);assert.equal(p.tab,'Criar');assert.ok(Number.isFinite(p.width))});
