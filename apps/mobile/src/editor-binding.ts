export interface EditorBinding {assetId:string;revision:number;faceId:string;candidateRevision:number}
export function acceptsResult(active:EditorBinding, completed:EditorBinding):boolean {
 return active.assetId===completed.assetId && active.revision===completed.revision && active.faceId===completed.faceId && active.candidateRevision===completed.candidateRevision;
}
// Also check current job ID, cancellation/tombstone and expiry before displaying.
