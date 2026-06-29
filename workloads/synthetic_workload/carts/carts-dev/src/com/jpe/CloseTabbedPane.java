package com.jpe;

import java.awt.Graphics;
import javax.swing.*;

public class CloseTabbedPane extends JTabbedPane {
	private TabCloseUI closeUI;

	public CloseTabbedPane() {
		closeUI = new TabCloseUI();
		closeUI.setTabbedPane(this);
		addMouseMotionListener(closeUI);
		addMouseListener(closeUI);
	}

	public void paint(Graphics g) {
		super.paint(g);
		closeUI.paint(g);
	}
}
