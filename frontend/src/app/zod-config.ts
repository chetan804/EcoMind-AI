import { z } from 'zod';

// Zod otherwise probes `new Function('')` to decide whether it may compile validators, which a
// Content-Security-Policy without 'unsafe-eval' reports as a violation. Interpreted parsing is
// plenty fast for the payload sizes here. Import this module before any schema is created.
z.config({ jitless: true });
