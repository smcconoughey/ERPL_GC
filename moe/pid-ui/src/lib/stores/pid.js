import { writable, derived } from 'svelte/store';

export const pidGrid = writable(null);
export const pidConfig = writable({});
export const pidFileName = writable('');
export const pidLoaded = derived(pidGrid, $g => $g !== null && $g.length > 0);
