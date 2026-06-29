package edu.penn.rtg.schedulingapp.old;

import java.awt.Dimension;
import javax.swing.JFrame;
import javax.swing.JLabel;

/**
 * A quick and dirty popup message class.
 * 
 */
public class PopupException extends JFrame {

	/**
	 * Creates a new instance of <code>PopupException</code> without detail
	 * message.
	 */
	public PopupException() {
	}

	/**
	 * Constructs an instance of <code>PopupException</code> with the specified
	 * detail message.
	 * 
	 * @param msg
	 *            the detail message.
	 */
	public PopupException(String msg) {
		super(msg);
		JLabel label = new JLabel(msg);
		JFrame frame = new JFrame("An Error has Occurred");
		frame.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE);
		frame.add(label);
		frame.setSize(new Dimension(400, 100));
		frame.setVisible(true);
	}
}
