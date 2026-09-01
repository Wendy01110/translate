import QtQuick
import QtQuick.Controls

Control {
    id: control

    property alias text: editor.text
    property alias readOnly: editor.readOnly
    property alias placeholderText: editor.placeholderText
    property bool emphasized: false

    Theme { id: theme }

    implicitWidth: 280
    implicitHeight: 220

    function forceEditorFocus() {
        editor.forceActiveFocus()
    }

    background: Rectangle {
        color: control.readOnly ? "#FBFCFE" : theme.surface
        radius: 10
        border.width: control.activeFocus || editor.activeFocus ? 1.5 : 1
        border.color: control.activeFocus || editor.activeFocus ? theme.accent : theme.border
    }

    contentItem: TextArea {
        id: editor
        leftPadding: 16
        rightPadding: 16
        topPadding: 15
        bottomPadding: 15
        wrapMode: TextEdit.Wrap
        selectByMouse: true
        persistentSelection: true
        color: theme.textPrimary
        selectionColor: theme.accentSoft
        selectedTextColor: theme.textPrimary
        placeholderTextColor: theme.textTertiary
        font.family: theme.fontFamily
        font.pixelSize: control.emphasized ? 17 : 16
        background: null
        verticalAlignment: TextEdit.AlignTop

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }
    }
}
