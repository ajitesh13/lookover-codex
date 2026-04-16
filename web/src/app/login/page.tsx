import { AuthShell } from "../_components/auth-shell";

export const metadata = {
  title: "Lookover Codex | Login",
  description: "Demo reviewer authentication.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ next?: string }>;
}) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const nextPath =
    typeof resolvedSearchParams.next === "string" && resolvedSearchParams.next.startsWith("/")
      ? resolvedSearchParams.next
      : "/compliance";
  return <AuthShell mode="login" nextPath={nextPath} />;
}
