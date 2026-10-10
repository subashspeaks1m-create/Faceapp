// Wire declarations. JSON Schema/Pydantic remains runtime validation authority.
export type FilterId = 'age_young'|'age_teen'|'age_50s'|'age_70s'|'smile_subtle'|'smile_tooth'|'laugh'|'gender_feminine'|'gender_masculine'|'hair_color'|'beard_density'|'beauty_retouch';
export type JobState = 'queued'|'running'|'succeeded'|'failed'|'cancel_requested'|'canceled'|'expired'|'purged';
export interface Options { color_hex?: string|null; skin_smoothing?: number|null; makeup?: number|null; }
export interface TransformRequest { asset_id:string; face_id:string; filter_type:FilterId; intensity:number; preserve_background?:boolean; source_revision:number; candidate_revision:number; options?:Options; }
export interface ConsentRequest { policy_version:string; purpose:'portrait_editing'; processor_region:'us'|'eu'; }
export interface ConsentReceipt { consent_receipt_id:string; policy_version:string; purpose:'portrait_editing'; processor_region:'us'|'eu'; accepted_at:string; withdrawn_at?:string|null; }
export interface UploadRequest { mime_type:'image/jpeg'|'image/png'|'image/heic'; byte_length:number; checksum_sha256:string; consent_receipt_id:string; }
export interface UploadGrant { asset_id:string; upload_url:string; method:'PUT'; required_headers:Record<string,string>; expires_at:string; absolute_purge_at:string; }
export interface UploadComplete {checksum_sha256:string}
export interface AssetReceipt {asset_id:string; normalized_width:number; normalized_height:number; faces:string[]; expires_at:string}
export interface SafeError {code:string; message:string; retryable:boolean; request_id:string}
export interface JobPayload {job_id:string; asset_id:string; face_id:string; source_revision:number; candidate_revision:number; status:JobState; stage:'queued'|'decode'|'detect'|'align'|'parse'|'transform'|'restore'|'blend'|'encode'|'deliver'|'done'; event_revision:number; progress_percent?:number|null; progress_source?:'indeterminate'|'measured_steps'|'complete'; result_cdn_url?:string|null; result_expires_at?:string|null; error?:SafeError|null; created_at:string; updated_at:string}
export interface DeletionReceipt {job_id:string;status:'requested'|'deleting'|'complete'|'partial_failure';requested_at:string}
// Runtime cross-field constraints (options compatibility, result grants, progress) are
// enforced by Pydantic. Generate schema-derived TS types before expanding this API.
