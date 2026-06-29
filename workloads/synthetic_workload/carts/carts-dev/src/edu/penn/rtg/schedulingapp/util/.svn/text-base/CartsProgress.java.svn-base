package edu.penn.rtg.schedulingapp.util;


import javax.swing.JFrame;
import javax.swing.JProgressBar;

@SuppressWarnings("serial")
public class CartsProgress extends JFrame {
	public static boolean isApp=false;
	JProgressBar progressBar;
	int val=0;
	int end=0;
	public CartsProgress(int end)
	{
		setTitle("Analyzing");
		this.end=end;
		progressBar = new JProgressBar(0, end);
		progressBar.setValue(val);
		progressBar.setStringPainted(true);
		progressBar.setIndeterminate(true);
		//this.setModal(true);
		if(isApp) {
			this.setDefaultCloseOperation(EXIT_ON_CLOSE);
		} else {
			this.setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
		}
		this.setAlwaysOnTop(true);
		getContentPane().add(progressBar);
		pack();
		setLocationRelativeTo(getRootPane());
	}
	public void setValue(int val)
	{
		progressBar.setValue(val);
	}
	public void increment() {
		if(progressBar.isIndeterminate())
			progressBar.setIndeterminate(false);
		val+=1;
		if(val>end) 
			val=0;
		//System.out.println(val);
		progressBar.setValue(val);
		this.requestFocus();
	}
	public void end() {
		setVisible(false);
		dispose();
	}
	public static void main(String[] args) {
		CartsProgress cp=new CartsProgress(10);
		cp.setVisible(true);
		for(int i=0;i<48;i++) {
			cp.increment();
		}
	}
}
