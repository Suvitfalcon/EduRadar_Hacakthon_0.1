import { createContext } from "react";

/* Holds the signed-in teacher (set by AuthGate) so the top bar can show their name. */
export const TeacherContext = createContext(null);
