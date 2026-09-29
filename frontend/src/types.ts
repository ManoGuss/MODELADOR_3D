export type Workspace = {grid:boolean; environment:boolean; overlays:boolean; camera:number[]; target:number[]};
export type Project = {id:string; name:string; revision:number; workspace:Workspace; updated_at:string; asset_count:number};
export type Provider = {id:string;name:string;status:string;reason:string};
export type Diagnostic = {os:string;cpu:string;cores:number;ram_bytes:number;ram_available_bytes:number;gpu:{status:string;devices:{name:string;vram_mb:string;driver:string}[];reason:string|null};python:string;blender:string|null;comfyui:string;storage:string;free_bytes:number;cuda:string;rocm:string};
