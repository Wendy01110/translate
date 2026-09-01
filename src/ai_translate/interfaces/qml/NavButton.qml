import QtQuick
import QtQuick.Controls

Button {
    id: control

    property bool selected: false

    Theme { id: theme }

    implicitHeight: 48
    leftPadding: 22
    rightPadding: 14

    contentItem: Text {
        text: control.text
        color: control.selected ? theme.accent : theme.textPrimary
        font.family: theme.fontFamily
        font.pixelSize: 15
        font.weight: control.selected ? Font.DemiBold : Font.Normal
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        color: control.selected ? theme.accentSoft : (control.hovered ? theme.surfaceMuted : "transparent")
        radius: 8

        Rectangle {
            visible: control.selected
            width: 3
            height: 26
            radius: 1.5
            color: theme.accent
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
