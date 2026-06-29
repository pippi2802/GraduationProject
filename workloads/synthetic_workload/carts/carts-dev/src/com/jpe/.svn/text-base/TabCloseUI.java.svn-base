package com.jpe;

import java.awt.*;
import java.awt.event.*;

import javax.swing.JOptionPane;

public class TabCloseUI implements MouseListener, MouseMotionListener {
	private CloseTabbedPane tabbedPane;
	private int closeX = 0, closeY = 0, meX = 0, meY = 0;
	private int selectedTab;

	public void mouseEntered(MouseEvent me) {
	}

	public void mouseExited(MouseEvent me) {
	}

	public void mousePressed(MouseEvent me) {
	}

	public void mouseReleased(MouseEvent me) {
	}

	public void mouseDragged(MouseEvent me) {
	}

	public void mouseClicked(MouseEvent me) {
		if (closeUnderMouse(me.getX(), me.getY())) {
			int choice = JOptionPane.showConfirmDialog(null,
					"Do you want to close this tab?", "Confirmation Dialog",
					JOptionPane.INFORMATION_MESSAGE);
			if (choice == 0) {
				jpe.singleInstance.close("");
			}
			selectedTab = tabbedPane.getSelectedIndex();
		}
	}

	public void mouseMoved(MouseEvent me) {
		meX = me.getX();
		meY = me.getY();
		if (mouseOverTab(meX, meY)) {
			controlCursor();
			tabbedPane.repaint();
		}
	}

	private void controlCursor() {
		if (tabbedPane.getTabCount() > 0)
			if (closeUnderMouse(meX, meY)) {
				tabbedPane.setCursor(new Cursor(Cursor.HAND_CURSOR));
				if (selectedTab > -1)
					tabbedPane.setToolTipTextAt(selectedTab, "Close "
							+ tabbedPane.getTitleAt(selectedTab));
			} else {
				tabbedPane.setCursor(new Cursor(Cursor.DEFAULT_CURSOR));
				if (selectedTab > -1)
					tabbedPane.setToolTipTextAt(selectedTab, "");
			}
	}

	private boolean closeUnderMouse(int x, int y) {
		return new Rectangle(closeX - 2, closeY - 5, 10, 10).contains(x, y);
	}

	public void paint(Graphics g) {
		if (mouseOverTab(meX, meY)) {
			drawClose(g, closeX, closeY);
		}
		int tabCount = tabbedPane.getTabCount();
		for (int j = 0; j < tabCount; j++)
			if (tabbedPane.getComponent(j).isShowing()) {
				int x = tabbedPane.getBoundsAt(j).x
						+ tabbedPane.getBoundsAt(j).width - 12;
				int y = tabbedPane.getBoundsAt(j).y + 14;
				drawClose(g, x, y);
				break;
			}
	}

	private void drawClose(Graphics g, int x, int y) {
		if (tabbedPane != null && tabbedPane.getTabCount() > 0) {
			Graphics2D g2 = (Graphics2D) g;
			g2.setStroke(new BasicStroke(1, BasicStroke.JOIN_ROUND,
					BasicStroke.CAP_ROUND));
			g2.setColor(Color.DARK_GRAY);
			if (isUnderMouse(x, y)) {
				drawColored(g2, Color.BLACK, x, y);
			} else {
				drawColored(g2, Color.WHITE, x, y);
			}
		}

	}

	private void drawColored(Graphics2D g2, Color color, int x, int y) {
		// g2.drawLine(x, y, x + 8, y - 8);
		// g2.drawLine(x + 8, y, x, y - 8);
		// g2.setColor(color);
		// g2.setStroke(new BasicStroke(2, BasicStroke.JOIN_ROUND,
		// BasicStroke.CAP_ROUND));
		// g2.drawLine(x, y, x + 8, y - 8);
		// g2.drawLine(x + 8, y, x, y - 8);

		int y1 = y - 2;
		g2.drawLine(x, y1, x + 8, y1 - 8);
		g2.drawLine(x + 8, y1, x, y1 - 8);
		g2.setColor(color);
		g2.setStroke(new BasicStroke(2, BasicStroke.JOIN_ROUND,
				BasicStroke.CAP_ROUND));
		g2.drawLine(x, y1, x + 8, y1 - 8);
		g2.drawLine(x + 8, y1, x, y1 - 8);
	}

	private boolean isUnderMouse(int x, int y) {
		if (Math.abs(x - meX + 3) < 6 && Math.abs(y - meY - 4) < 6)
			return true;
		return false;
	}

	private boolean mouseOverTab(int x, int y) {
		int tabCount = tabbedPane.getTabCount();
		for (int j = 0; j < tabCount; j++)
			if (tabbedPane.getBoundsAt(j).contains(meX, meY)) {
				selectedTab = j;
				closeX = tabbedPane.getBoundsAt(j).x
						+ tabbedPane.getBoundsAt(j).width - 12;
				closeY = tabbedPane.getBoundsAt(j).y + 14;
				return true;
			}
		return false;
	}

	public void setTabbedPane(CloseTabbedPane ctp) {
		tabbedPane = ctp;
	}
}
