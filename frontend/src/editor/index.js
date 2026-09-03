import editor from "./editor"
import { activateLivePreviews } from "./live-preview"

export default editor

export { activateLivePreviews }

export function activateEditors() {
  document
    .querySelectorAll("[misago-editor-active='false']")
    .forEach(editor.activate)
}
