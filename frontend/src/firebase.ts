import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  type Auth,
  initializeAuth,
  inMemoryPersistence,
} from "firebase/auth";
import { getFirestore, connectFirestoreEmulator, type Firestore } from "firebase/firestore";
import type { PublicConfig } from "./types";

let app: FirebaseApp | null = null;
let authInstance: Auth | null = null;
let dbInstance: Firestore | null = null;

// Instancia separada para leitor publico, com persistencia em memoria, para que
// abrir um link publico nao substitua o login comum existente (secao 10.3).
let publicApp: FirebaseApp | null = null;
let publicAuth: Auth | null = null;
let publicDb: Firestore | null = null;

export function initFirebase(cfg: PublicConfig): void {
  if (app) return;
  app = initializeApp({
    apiKey: cfg.firebaseApiKey,
    authDomain: cfg.firebaseAuthDomain,
    projectId: cfg.firebaseProjectId,
    appId: cfg.firebaseAppId,
  });
  authInstance = getAuth(app);
  dbInstance = getFirestore(app);
  if (cfg.usingEmulators) {
    if (cfg.authEmulatorHost) {
      connectAuthEmulator(authInstance, `http://${cfg.authEmulatorHost}`, {
        disableWarnings: true,
      });
    }
    if (cfg.firestoreEmulatorHost) {
      const [host, port] = cfg.firestoreEmulatorHost.split(":");
      connectFirestoreEmulator(dbInstance, host, Number(port));
    }
  }
}

export function initPublicFirebase(cfg: PublicConfig): { auth: Auth; db: Firestore } {
  if (!publicApp) {
    publicApp = initializeApp(
      {
        apiKey: cfg.firebaseApiKey,
        authDomain: cfg.firebaseAuthDomain,
        projectId: cfg.firebaseProjectId,
        appId: cfg.firebaseAppId,
      },
      "public-view",
    );
    publicAuth = initializeAuth(publicApp, { persistence: inMemoryPersistence });
    publicDb = getFirestore(publicApp);
    if (cfg.usingEmulators) {
      if (cfg.authEmulatorHost) {
        connectAuthEmulator(publicAuth, `http://${cfg.authEmulatorHost}`, {
          disableWarnings: true,
        });
      }
      if (cfg.firestoreEmulatorHost) {
        const [host, port] = cfg.firestoreEmulatorHost.split(":");
        connectFirestoreEmulator(publicDb, host, Number(port));
      }
    }
  }
  return { auth: publicAuth!, db: publicDb! };
}

export function auth(): Auth {
  if (!authInstance) throw new Error("Firebase nao inicializado.");
  return authInstance;
}

export function db(): Firestore {
  if (!dbInstance) throw new Error("Firebase nao inicializado.");
  return dbInstance;
}
