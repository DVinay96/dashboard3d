import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatementEditor } from "./statement-editor";
import type { ModuleInfo, Project, Statement } from "@/api/types";

const modules: ModuleInfo[] = [
  {
    id: "catalog",
    label: "Catalogo",
    description: "",
    actions: [
      { name: "products:list", description: "Ver" },
      { name: "products:delete", description: "Borrar" },
    ],
  },
  {
    id: "brands",
    label: "Marcas",
    description: "",
    actions: [{ name: "brands:read", description: "Ver marcas" }],
  },
];
const projects = [{ id: "p1", name: "Otoño" }] as Project[];
const initial: Statement[] = [
  { effect: "allow", actions: ["products:list"], resources: ["*"] },
];

describe("StatementEditor", () => {
  it("un clic en una accion la agrega al statement activo", async () => {
    const onChange = vi.fn();
    render(
      <StatementEditor
        initial={initial}
        modules={modules}
        projects={projects}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "brands:read" }));
    expect(onChange).toHaveBeenLastCalledWith([
      {
        effect: "allow",
        actions: ["products:list", "brands:read"],
        resources: ["*"],
      },
    ]);
  });

  it("ofrece comodines por familia, sin duplicarlos", () => {
    render(
      <StatementEditor
        initial={initial}
        modules={modules}
        projects={projects}
        onChange={() => {}}
      />,
    );
    expect(screen.getAllByRole("button", { name: "products:*" })).toHaveLength(
      1,
    );
    expect(
      screen.getByRole("button", { name: "brands:*" }),
    ).toBeInTheDocument();
  });

  it("acotar a un proyecto agrega el proyecto y sus productos", async () => {
    const onChange = vi.fn();
    render(
      <StatementEditor
        initial={[
          { effect: "allow", actions: ["products:list"], resources: [] },
        ]}
        modules={modules}
        projects={projects}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Proyecto: Otoño" }),
    );
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ resources: ["project/p1", "project/p1/*"] }),
    ]);
  });

  it("no se come un salto de linea a medio escribir", async () => {
    const onChange = vi.fn();
    render(
      <StatementEditor
        initial={initial}
        modules={modules}
        projects={projects}
        onChange={onChange}
      />,
    );
    const box = screen.getByLabelText(/Acciones/);
    await userEvent.type(box, "{Enter}brands:read");
    expect(box).toHaveValue("products:list\nbrands:read");
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ actions: ["products:list", "brands:read"] }),
    ]);
  });

  it("cambia el efecto y quita statements", async () => {
    const onChange = vi.fn();
    render(
      <StatementEditor
        initial={initial}
        modules={modules}
        projects={projects}
        onChange={onChange}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Efecto del statement 1"),
      "deny",
    );
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ effect: "deny" }),
    ]);
    await userEvent.click(
      screen.getByRole("button", { name: "Quitar statement 1" }),
    );
    expect(onChange).toHaveBeenLastCalledWith([]);
  });
});
