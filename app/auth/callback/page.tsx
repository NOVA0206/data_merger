"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const hash = window.location.hash;
    const match = hash.match(/token=([^&]+)/);
    if (match) {
      window.localStorage.setItem("session_token", decodeURIComponent(match[1]));
    }
    router.replace("/");
  }, [router]);

  return <p className="p-8 text-slate-600">Signing you in…</p>;
}
