import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import type {Workspace} from '../types';
export function Viewport({workspace,onCamera,focus}:{workspace:Workspace;onCamera:(camera:number[],target:number[])=>void;focus:number}){
 const host=useRef<HTMLDivElement>(null); const sceneRef=useRef<{scene:THREE.Scene;grid:THREE.GridHelper;environment:THREE.Group;camera:THREE.PerspectiveCamera;controls:OrbitControls;render:()=>void}|undefined>(undefined);
 const callback=useRef(onCamera); callback.current=onCamera;
 const [error,setError]=useState('');
 useEffect(()=>{
  if(!host.current)return;
  let renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false})}catch{setError('Não foi possível iniciar o WebGL. Verifique a aceleração gráfica do navegador.');return}
  renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.outputColorSpace=THREE.SRGBColorSpace;
  host.current.appendChild(renderer.domElement);
  const scene=new THREE.Scene(); scene.background=new THREE.Color('#adc9d6'); scene.fog=new THREE.Fog('#adc9d6',45,150);
  const camera=new THREE.PerspectiveCamera(45,1,.1,500);camera.position.fromArray(workspace.camera);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.fromArray(workspace.target);controls.maxDistance=120;controls.minDistance=2;controls.maxPolarAngle=Math.PI*.49;controls.update();
  const environment=new THREE.Group();
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(600,600),new THREE.MeshStandardMaterial({color:'#a6b3ac',roughness:1}));ground.rotation.x=-Math.PI/2;ground.position.y=-.02;environment.add(ground);
  // Workspace scenery only. These clouds are never assets or generation results.
  for(const [x,y,z] of [[-45,12,-60],[30,14,-65],[65,13,-30]]){
   const cloud=new THREE.Mesh(new THREE.SphereGeometry(1,16,8),new THREE.MeshBasicMaterial({color:'#edf3f4',transparent:true,opacity:.5}));cloud.position.set(x,y,z);cloud.scale.set(14,1.4,4);environment.add(cloud);
  }
  scene.add(environment,new THREE.HemisphereLight('#ffffff','#657c67',2.6));const sun=new THREE.DirectionalLight('#fff5e6',2);sun.position.set(12,25,8);scene.add(sun);
  const grid=new THREE.GridHelper(100,50,'#708a89','#9baaa5');scene.add(grid);
  const render=()=>renderer.render(scene,camera);
  const end=()=>callback.current(camera.position.toArray(),controls.target.toArray());
  controls.addEventListener('change',render);controls.addEventListener('end',end);
  const observer=new ResizeObserver(()=>{if(!host.current)return;const {clientWidth:w,clientHeight:h}=host.current;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();render()});observer.observe(host.current);
  const lost=(e:Event)=>{e.preventDefault();setError('O contexto gráfico foi perdido. Recarregue a página para restaurar a viewport.')};renderer.domElement.addEventListener('webglcontextlost',lost);
  sceneRef.current={scene,grid,environment,camera,controls,render};render();
  return()=>{observer.disconnect();controls.dispose();scene.traverse(o=>{if(o instanceof THREE.Mesh||o instanceof THREE.LineSegments){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose())}});renderer.dispose();renderer.domElement.remove();sceneRef.current=undefined};
 },[]);
 useEffect(()=>{const s=sceneRef.current;if(s){s.grid.visible=workspace.grid;s.environment.visible=workspace.environment;s.scene.background=new THREE.Color(workspace.environment?'#adc9d6':'#202c32');s.scene.fog=workspace.environment?new THREE.Fog('#adc9d6',45,150):null;s.render()}},[workspace.grid,workspace.environment]);
 useEffect(()=>{const s=sceneRef.current;if(s){s.camera.position.fromArray(workspace.camera);s.controls.target.fromArray(workspace.target);s.controls.update();s.render()}},[workspace.camera,workspace.target]);
 useEffect(()=>{if(focus){const s=sceneRef.current;if(s){s.camera.position.set(12,4,12);s.controls.target.set(0,0,0);s.controls.update();callback.current(s.camera.position.toArray(),s.controls.target.toArray())}}},[focus]);
 return <div ref={host} className="viewport" aria-label="Viewport 3D">{error&&<div className="viewport-error" role="alert">{error}</div>}</div>
}

