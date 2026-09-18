"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, SESSION_COOKIE, secureCookies } from "@/lib/api";

export type FormState = { error?: string; success?: string };

export async function login(_prev: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  let res: Response;
  try {
    res = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return { error: "Peak is unavailable. Try again shortly." };
  }
  if (res.status === 401 || res.status === 422) return { error: "Incorrect email or password." };
  if (!res.ok) return { error: "Sign-in failed. Try again shortly." };

  const { token, max_age } = await res.json();
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookies(),
    path: "/",
    maxAge: max_age,
  });
  redirect("/dashboard");
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch {
    // The session token is stateless; clearing the cookie below is what signs the user out.
  }
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}

export async function addConsultant(_prev: FormState, formData: FormData): Promise<FormState> {
  const name = String(formData.get("name") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();
  const role = String(formData.get("role") ?? "consultant");
  const password = String(formData.get("password") ?? "");
  if (password !== String(formData.get("confirm") ?? "")) {
    return { error: "Passwords do not match." };
  }

  // The Python API enforces the Admin role; this action adds no authorization of its own.
  const res = await apiFetch("/consultants", {
    method: "POST",
    body: JSON.stringify({ name, email, role, password }),
  });
  if (res.status === 401) redirect("/login");
  if (res.status === 403) return { error: "Only an Admin can add consultants." };
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    return {
      error:
        typeof detail?.message === "string"
          ? detail.message
          : "Check the details: name, a valid email, and a password of at least 12 characters.",
    };
  }
  revalidatePath("/consultants");
  return { success: `${name} can now sign in.` };
}
