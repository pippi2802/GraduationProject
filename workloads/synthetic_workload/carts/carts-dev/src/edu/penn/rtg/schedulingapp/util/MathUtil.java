package edu.penn.rtg.schedulingapp.util;

import java.util.Vector;

import edu.penn.rtg.schedulingapp.basic.PTask;


public class MathUtil {
	public static int computeLCM(Vector<PTask> tasks)
	{
		int lcm = 0, gcd = 0;
		int number1 = 0, number2 = 0;
		for(int idx=0;idx<tasks.size();idx++)
		{
			if(idx==0)
			{
				number1=tasks.elementAt(idx).period;
				lcm=number1;
				continue;
			}
			number2=tasks.elementAt(idx).period;
			gcd = generateGCD(number1, number2);
			lcm = number1 * number2 / gcd;
			number1 = lcm;
		}
		return lcm;
	}

	private static int generateGCD(int number1, int number2) {

		if (number1 >= number2) {
			if (number2 == 0)
				return number1;
			else {
				int remainder = (int) (number1 - Math.floor(number1 / number2)
						* number2);
				return generateGCD(number2, remainder);
			}
		} else {
			if (number1 == 0)
				return number2;
			else {
				int remainder = (int) (number2 - Math.floor(number2 / number1)
						* number1);
				return generateGCD(number1, remainder);
			}
		}
	}

}
