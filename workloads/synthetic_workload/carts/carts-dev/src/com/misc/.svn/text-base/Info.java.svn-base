/* This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

//Info.java - this class uses various methods of the System class to display system
//information to the user.
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk

package com.misc;

import java.awt.event.ActionListener;
import java.awt.event.ActionEvent;
import java.awt.event.WindowEvent;

import java.awt.FlowLayout;
import java.awt.Dimension;
import java.awt.BorderLayout;

import javax.swing.JPanel;
import javax.swing.JLabel;
import javax.swing.JScrollPane;
import javax.swing.JButton;
import javax.swing.JDialog;
import javax.swing.BoxLayout;
import javax.swing.Box;
import javax.swing.BorderFactory;

import com.jpe.jpe;
import com.utils.*;

public class Info extends JDialog implements ActionListener {

	private JPanel butpanel, mainPanel, topPanel, midPanel, botPanel;
	private JLabel topLabel, midLabel, botLabel;
	private JButton jbtClose;
	private Utils Utils;

	public Info(jpe win) {

		super(win, "System Information", true);
		setResizable(false);
		setSize(400, 300);

		topLabel = new JLabel();
		midLabel = new JLabel();
		botLabel = new JLabel();

		String home = System.getProperty("user.home");
		String name = System.getProperty("user.name");
		String dir = System.getProperty("user.dir");

		String os = System.getProperty("os.name");
		String ver = System.getProperty("os.version");
		String arc = System.getProperty("os.arch");

		String javer = System.getProperty("java.version");
		String vendor = System.getProperty("java.vendor");
		String url = System.getProperty("java.vendor.url");
		String inst = System.getProperty("java.home");
		String s = System.getProperty("java.class.path");

		String path = new String(Utils.splitOnToken(s, ";"));

		Runtime.getRuntime().gc();
		long freemem = (Runtime.getRuntime().freeMemory() / (100000));
		long totmem = (Runtime.getRuntime().totalMemory() / (100000));

		topLabel.setText("<HTML><font face = arial size = 2 color = 000000>"
				+ " <BR> &nbsp&nbsp  Home directory - " + home + " &nbsp "
				+ "<BR> &nbsp&nbsp  User Name - " + name + " &nbsp "
				+ "<BR> &nbsp&nbsp  Working dir - " + dir + " &nbsp "
				+ "</font>");

		midLabel.setText("<HTML><font face = arial size = 2 color = 000000>"
				+ "<BR> &nbsp&nbsp  Operating System - " + os + " &nbsp "
				+ "<BR> &nbsp&nbsp  System  Architecture - " + arc + " &nbsp "
				+ "<BR> &nbsp&nbsp  System Version - " + ver + " &nbsp "
				+ "<BR> &nbsp&nbsp  Free memory - " + "@ " + freemem + "Mb"
				+ " &nbsp " + "<BR> &nbsp&nbsp  Memory available to Java - "
				+ "@ " + totmem + "Mb" + " &nbsp " + "</font>");

		botLabel.setText("<HTML><font face = arial size = 2 color = 000000>"
				+ "<BR> &nbsp&nbsp  Java version - " + javer + " &nbsp "
				+ "<BR> &nbsp&nbsp  Vendor - " + vendor + " &nbsp "
				+ "<BR> &nbsp&nbsp  Url - " + url + " &nbsp "
				+ "<BR> &nbsp&nbsp  Installation dir - " + inst + " &nbsp "
				+ "<BR> &nbsp&nbsp  Classpath - " + path + " &nbsp "
				+ "</font>");

		topPanel = new JPanel();
		topPanel.setBorder(BorderFactory.createTitledBorder(BorderFactory
				.createEtchedBorder(), "User"));
		topPanel.setLayout(new BoxLayout(topPanel, BoxLayout.Y_AXIS));
		topPanel.add(Box.createGlue());
		topPanel.add(topLabel);

		midPanel = new JPanel();
		midPanel.setBorder(BorderFactory.createTitledBorder(BorderFactory
				.createEtchedBorder(), "O.S"));
		midPanel.setLayout(new BoxLayout(midPanel, BoxLayout.Y_AXIS));
		midPanel.add(Box.createGlue());
		midPanel.add(midLabel);

		botPanel = new JPanel();
		botPanel.setBorder(BorderFactory.createTitledBorder(BorderFactory
				.createEtchedBorder(), "Java[tm]"));
		botPanel.setLayout(new BoxLayout(botPanel, BoxLayout.Y_AXIS));
		botPanel.add(Box.createGlue());
		botPanel.add(botLabel);

		mainPanel = new JPanel();
		mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));

		mainPanel.add(topPanel);
		mainPanel.add(Box.createGlue());
		mainPanel.add(midPanel);
		mainPanel.add(Box.createGlue());
		mainPanel.add(botPanel);

		JScrollPane jsp = new JScrollPane(mainPanel);

		butpanel = new JPanel();
		butpanel.setLayout(new FlowLayout(FlowLayout.CENTER));
		butpanel.add(jbtClose = new JButton("OK"));
		jbtClose.setPreferredSize(new Dimension(55, 20));

		getContentPane().setLayout(new BorderLayout());
		getContentPane().add(jsp, BorderLayout.CENTER);
		getContentPane().add(butpanel, BorderLayout.SOUTH);

		// Register listener
		jbtClose.addActionListener(this);

		pack();

		Utils.centerComponent(this);
		setVisible(true);
	}

	protected void processWindowEvent(WindowEvent e) {
		if (e.getID() == WindowEvent.WINDOW_CLOSING) {
			cancel();
		}
		super.processWindowEvent(e);
	}

	void cancel() {
		dispose();
	}

	public void actionPerformed(ActionEvent e) {
		if (e.getSource() == jbtClose) {
			cancel();
		}
	}
}
