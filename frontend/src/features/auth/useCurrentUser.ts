import { useCallback, useEffect, useState } from "react";
import { getMe, logout, type User } from "../../api/auth";

/**
 * Who is signed in, for public pages. `undefined` while checking, `null` when nobody is
 * (or the server can't be reached: public pages then just offer "Log in").
 */
export function useCurrentUser() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    getMe()
      .then((me) => active && setUser(me))
      .catch(() => active && setUser(null));
    return () => {
      active = false;
    };
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  }, []);

  return { user, signOut };
}
