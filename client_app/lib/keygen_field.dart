/// Product keygen entry field — must accept system clipboard paste.
///
/// Used by the forced **Enter licence keygen** sheet and Settings
/// **Payment entitlement / keygen** control. Paste paths:
/// - Cmd/Ctrl+V and the platform text-field paste shortcut (EditableText)
/// - Context-menu Paste (interactive selection + toolbar)
/// - Explicit **Paste** suffix control ([kKeygenPasteButtonKey]) via
///   [pasteKeygenFromClipboard] for surfaces where modal focus steals shortcuts
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Finder key for the shipped keygen [TextField].
const Key kKeygenTextFieldKey = Key('keygen_entry_text_field');

/// Finder key for the explicit Paste control on the keygen field.
const Key kKeygenPasteButtonKey = Key('keygen_entry_paste_button');

/// Tooltip / semantics for the Paste control.
const String kKeygenPasteTooltip = 'Paste keygen from clipboard';

/// Read plain text from the system clipboard into [controller].
///
/// Returns true when non-empty clipboard text was applied. Does not trim or
/// uppercase — [LicenceGate.importKeygenAndVerify] normalizes on verify.
Future<bool> pasteKeygenFromClipboard(TextEditingController controller) async {
  final data = await Clipboard.getData(Clipboard.kTextPlain);
  final text = data?.text;
  if (text == null || text.isEmpty) {
    return false;
  }
  controller.value = TextEditingValue(
    text: text,
    selection: TextSelection.collapsed(offset: text.length),
  );
  return true;
}

/// Whether a product keygen [TextField] is configured to accept paste.
///
/// Structural contract for the unlock fields: editable, interactive selection
/// on, no input formatters that could swallow a normal keygen paste.
bool keygenFieldAllowsPaste(TextField field) {
  if (field.readOnly) return false;
  if (field.enabled == false) return false;
  // null means default true on TextField
  if (field.enableInteractiveSelection == false) return false;
  final formatters = field.inputFormatters;
  if (formatters != null && formatters.isNotEmpty) return false;
  return true;
}

/// Shipped keygen entry control (sheet + Settings).
class KeygenEntryField extends StatelessWidget {
  const KeygenEntryField({
    super.key,
    required this.controller,
    this.labelText = 'RPT-KEY-…',
    this.enabled = true,
    this.autofocus = false,
    this.isDense = false,
    this.style,
    this.onChanged,
  });

  final TextEditingController controller;
  final String labelText;
  final bool enabled;
  final bool autofocus;
  final bool isDense;
  final TextStyle? style;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) {
    return TextField(
      key: kKeygenTextFieldKey,
      controller: controller,
      enabled: enabled,
      autofocus: autofocus,
      // Explicit true: never inherit a parent that disabled selection/paste.
      enableInteractiveSelection: true,
      readOnly: false,
      enableSuggestions: false,
      autocorrect: false,
      smartDashesType: SmartDashesType.disabled,
      smartQuotesType: SmartQuotesType.disabled,
      // Avoid OS “password” secure-field paste quirks; still plain text.
      keyboardType: TextInputType.text,
      textCapitalization: TextCapitalization.none,
      textInputAction: TextInputAction.done,
      style: style,
      onChanged: onChanged,
      // Default toolbar includes Paste; keep explicit for desktop/modal sheets.
      contextMenuBuilder: (context, editableTextState) {
        return AdaptiveTextSelectionToolbar.editableText(
          editableTextState: editableTextState,
        );
      },
      decoration: InputDecoration(
        labelText: labelText,
        border: const OutlineInputBorder(),
        isDense: isDense,
        suffixIcon: IconButton(
          key: kKeygenPasteButtonKey,
          tooltip: kKeygenPasteTooltip,
          icon: const Icon(Icons.content_paste),
          onPressed: !enabled
              ? null
              : () async {
                  await pasteKeygenFromClipboard(controller);
                },
        ),
      ),
    );
  }
}
