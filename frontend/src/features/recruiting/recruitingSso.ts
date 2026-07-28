type RecruitmentAuthWindow = {
  close: () => void;
  location: { replace: (url: string) => void };
};

type RecruitmentAuthResult = {
  message?: string;
  ready: boolean;
  url?: string;
};

type StartRecruitmentSsoOptions = {
  loadAuthUrl: () => Promise<RecruitmentAuthResult>;
  openWindow: () => RecruitmentAuthWindow | null;
  saveDraft: () => Promise<unknown>;
};

export async function startRecruitmentSso({ loadAuthUrl, openWindow, saveDraft }: StartRecruitmentSsoOptions) {
  const authWindow = openWindow();
  if (!authWindow) throw new Error("Your browser blocked the EVE SSO tab. Allow pop-ups for EQM and try again.");

  try {
    await saveDraft();
    const result = await loadAuthUrl();
    if (!result.ready || !result.url) throw new Error(result.message || "EVE SSO is not configured.");
    authWindow.location.replace(result.url);
  } catch (error) {
    authWindow.close();
    throw error;
  }
}