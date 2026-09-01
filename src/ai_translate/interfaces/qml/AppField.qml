import QtQuick
import QtQuick.Controls

TextField {
    id: control

    property bool secret: false

    Theme { id: theme }

    implicitHeight: 42
    leftPadding: 13
    rightPadding: 13
    color: theme.textPrimary
    placeholderTextColor: theme.textTertiary
    selectionColor: theme.accentSoft
    selectedTextColor: theme.textPrimary
    font.family: theme.fontFamily
    font.pixelSize: 14
    echoMode: secret ? TextInput.Password : TextInput.Normal

    background: Rectangle {
        color: theme.surface
        radius: 8
        border.width: control.activeFocus ? 1.5 : 1
        border.color: control.activeFocus ? theme.accent : theme.border
    }
}
