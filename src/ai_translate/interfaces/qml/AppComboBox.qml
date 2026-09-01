import QtQuick
import QtQuick.Controls

ComboBox {
    id: control

    Theme { id: theme }

    implicitHeight: 42
    leftPadding: 13
    rightPadding: 38
    font.family: theme.fontFamily
    font.pixelSize: 14

    indicator: Image {
        x: control.width - width - 12
        y: (control.height - height) / 2
        width: 18
        height: 18
        source: "icons/chevron-down.svg"
        opacity: control.enabled ? 1 : 0.45
    }

    background: Rectangle {
        color: theme.surface
        radius: 8
        border.width: control.activeFocus ? 1.5 : 1
        border.color: control.activeFocus ? theme.accent : theme.border
    }
}
