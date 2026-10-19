import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fail, mockApi, ok } from "../../test/mockApi";
import { SiteHeader } from "./SiteHeader";

const patient = {
  id: 6,
  email: "patient@demo.citycare.pk",
  fullName: "Ali Patient",
  phone: "",
  role: "patient",
  isStaff: false,
  hospital: null,
};

function renderHeader() {
  return render(
    <MemoryRouter>
      <SiteHeader />
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("SiteHeader", () => {
  it("offers log in and sign up when nobody is signed in", async () => {
    mockApi({ "GET /auth/me/": fail(403) });
    renderHeader();
    expect(
      await screen.findByRole("link", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Create account" }),
    ).toBeInTheDocument();
  });

  it("shows a signed-in patient their name and a log out button, not the staff link", async () => {
    mockApi({ "GET /auth/me/": ok(patient) });
    renderHeader();
    expect(await screen.findByText("Ali Patient")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Log in" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Staff workspace" }),
    ).not.toBeInTheDocument();
  });

  it("shows staff a link back to their workspace", async () => {
    mockApi({
      "GET /auth/me/": ok({
        ...patient,
        fullName: "Hina Javed",
        role: "nurse",
        isStaff: true,
      }),
    });
    renderHeader();
    expect(
      await screen.findByRole("link", { name: "Staff workspace" }),
    ).toHaveAttribute("href", "/staff");
  });

  it("logging out returns the header to log in / sign up", async () => {
    mockApi({
      "GET /auth/me/": ok(patient),
      "POST /auth/logout/": { status: 204 },
    });
    renderHeader();
    await userEvent.click(
      await screen.findByRole("button", { name: "Log out" }),
    );
    expect(
      await screen.findByRole("link", { name: "Log in" }),
    ).toBeInTheDocument();
  });
});
