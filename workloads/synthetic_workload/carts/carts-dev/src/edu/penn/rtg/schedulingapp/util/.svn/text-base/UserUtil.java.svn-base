package edu.penn.rtg.schedulingapp.util;

import java.awt.Frame;

import javax.swing.JOptionPane;

public class UserUtil {
	public static int select(String display,int start,int end)
	{
		Frame frame = new Frame();
		String str=JOptionPane.showInputDialog(frame,
				display);
		int val=-1;
		if(str.trim().equals(""))
		{
			showErr("Input value is empty. Drawing graph is canceled");
			return -1;
		}
		try{
			val=Integer.valueOf(str).intValue();
		}
		catch(Exception e)
		{
			showErr("Input value is not integer number. Drawing graph is canceled");
			return -1;
		}
		if(val>=start&&val<=end) {
			return val;
		}
		else
		{
			showErr("Range of input value should be from "+start+" to "+end+". Drawing graph is canceled");
			return -1;
		}
	}
	public static void show(String display)
	{
		Frame frame = new Frame();
		JOptionPane.showMessageDialog(frame,display,"CARTS",JOptionPane.INFORMATION_MESSAGE);
	}
	public static void showErr(String display)
	{
		Frame frame = new Frame();
		JOptionPane.showMessageDialog(frame,display,"CARTS",JOptionPane.ERROR_MESSAGE);
	}
	public static void show(String title,String display)
	{
		Frame frame = new Frame();
		JOptionPane.showMessageDialog(frame,display,title,JOptionPane.INFORMATION_MESSAGE);
	}
	public static int answerYN(String display,String title)
	{
		Frame frame = new Frame();
		int t=JOptionPane.showConfirmDialog(frame,display, title, JOptionPane.YES_NO_OPTION);
		return t;
	}
}
